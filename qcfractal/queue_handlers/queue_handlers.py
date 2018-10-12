"""
Queue backend abstraction manager.
"""

import logging
import traceback
import collections

from ..web_handlers import APIHandler
from .. import procedures
from .. import services


class QueueNanny:
    """
    This object maintains a computational queue and watches for finished jobs for different
    queue backends. Finished jobs are added to the database and removed from the queue.

    Attributes
    ----------
    storage_socket : StorageSocket
        A socket for the backend storage platform
    queue_adapter : QueueAdapter
        The DBAdapter class for queue abstraction
    errors : dict
        A dictionary of current errors
    logger : logging.logger. Optional, Default: None
        A logger for the QueueNanny
    """

    def __init__(self, queue_adapter, storage_socket, logger=None, max_tasks=1000, max_services=20):
        """Summary

        Parameters
        ----------
        queue_adapter : QueueAdapter
            The DBAdapter class for queue abstraction
        storage_socket : DBSocket
            A socket for the backend database
        logger : logging.Logger, Optional. Default: None
            A logger for the QueueNanny
        """
        self.queue_adapter = queue_adapter
        self.storage_socket = storage_socket
        self.errors = {}
        self.max_tasks = max_tasks
        self.max_services = max_services

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('QueueNanny')

    def update(self):
        """Examines the queue for completed jobs and adds successful completions to the database
        while unsuccessful are logged for future inspection

        """

        # Pivot data so that we group all results in categories
        new_results = collections.defaultdict(list)
        error_data = []

        for key, (result, parser, hooks) in self.queue_adapter.aquire_complete().items():
            try:

                # Successful job
                if result["success"] is True:
                    self.logger.info("Update: {}".format(key))
                    result["queue_id"] = key
                    new_results[parser].append((result, hooks))

                # Failed job
                else:
                    if "error" in result:
                        error = result["error"]
                    else:
                        error = "No error supplied"

                    self.logger.info("Computation key did not complete successfully:\n\t{}\n"
                                     "Because: {}".format(str(key), error))

                    error_data.append((key, error))
            except Exception as e:
                msg = "Internal FractalServer Error:\n" + traceback.format_exc()
                self.errors[key] = msg
                self.logger.info("update: ERROR\n{}".format(msg))
                error_data.append((key, msg))

        # Run output parsers
        completed = []
        hooks = []
        for k, v in new_results.items():
            ret = procedures.get_procedure_output_parser(k)(self.storage_socket, v)
            completed.extend(ret[0])
            error_data.extend(ret[1])
            hooks.extend(ret[2])

        # Handle hooks and complete jobs
        self.storage_socket.handle_hooks(hooks)
        self.storage_socket.queue_mark_complete(completed)
        self.storage_socket.queue_mark_error(error_data)

        # Get new jobs
        open_slots = max(0, self.max_tasks - self.queue_adapter.task_count())
        if open_slots == 0:
            return

        # Add new jobs to queue
        new_jobs = self.storage_socket.queue_get_next(n=open_slots)
        self.queue_adapter.submit_tasks(new_jobs)

    def update_services(self):
        """Runs through all active services and examines their current status.
        """

        # Grab current services
        current_services = self.storage_socket.get_services({"status": "RUNNING"})["data"]

        # Grab new services if we have open slots
        open_slots = max(0, self.max_services - len(current_services))
        if open_slots > 0:
            new_services = self.storage_socket.get_services({"status": "READY"}, limit=open_slots)["data"]
            current_services.extend(new_services)

        # Loop over the services and iterate
        running_services = 0
        new_procedures = []
        complete_ids = []
        for data in current_services:
            obj = services.build(data["service"], self.storage_socket, data)

            finished = obj.iterate()
            self.storage_socket.update_services([(data["id"], obj.get_json())])
            # print(obj.get_json())

            if finished is not False:

                # Add results to procedures, remove complete_ids
                new_procedures.append(finished)
                complete_ids.append(data["id"])
            else:
                running_services += 1

        # Add new procedures and services
        self.storage_socket.add_procedures(new_procedures)
        self.storage_socket.del_services(complete_ids)

        return running_services

    def await_results(self):
        """A synchronous method for testing or small launches
        that awaits job completion before adding all queued results
        to the database and returning.

        Returns
        -------
        TYPE
            Description
        """
        self.update()
        self.queue_adapter.await_results()
        self.update()
        return True

    def await_services(self, max_iter=10):
        """A synchronous method for testing or small launches
        that awaits all service completion before adding all service results
        to the database and returning.

        Returns
        -------
        TYPE
            Description
        """

        self.await_results()
        for x in range(1, max_iter + 1):
            self.logger.info("\nAwait services: Iteration {}\n".format(x))
            running_services = self.update_services()
            self.await_results()
            if running_services == 0:
                break

        return True

    def list_current_tasks(self):
        """Provides a list of tasks currently in the queue along
        with the associated keys

        Returns
        -------
        ret : list of tuples
            All jobs currently still in the database
        """
        return self.queue_adapter.list_tasks()


class QueueScheduler(APIHandler):
    """
    Takes in a data packet the contains the molecule_hash, modelchem and options objects.
    """

    def post(self):
        """Summary
        """
        self.authenticate("compute")

        # Grab objects
        storage = self.objects["storage_socket"]

        # Format tasks
        func = procedures.get_procedure_input_parser(self.json["meta"]["procedure"])
        full_tasks, complete_jobs, errors = func(storage, self.json)

        # Add tasks to queue
        ret = storage.queue_submit(full_tasks)
        self.logger.info("QUEUE: Added {} tasks.".format(ret["meta"]["n_inserted"]))

        ret["data"] = {"submitted": ret["data"], "completed": list(complete_jobs), "queue": ret["meta"]["duplicates"]}
        ret["meta"]["duplicates"] = []
        ret["meta"]["errors"].extend(errors)

        self.write(ret)

    # def get(self):

    #     # _check_auth(self.objects, self.request.headers)

    #     self.objects["db_socket"].set_project(header["project"])
    #     queue_nanny = self.objects["queue_nanny"]
    #     ret = {}
    #     ret["queue"] = list(queue_nanny.queue)
    #     ret["error"] = queue_nanny.errors
    #     self.write(ret)


class ServiceScheduler(APIHandler):
    """
    Takes in a data packet the contains the molecule_hash, modelchem and options objects.
    """

    def post(self):
        """Summary
        """
        self.authenticate("compute")

        # Grab objects
        storage = self.objects["storage_socket"]

        # Figure out initial molecules
        errors = []
        ordered_mol_dict = {x: mol for x, mol in enumerate(self.json["data"])}
        mol_query = storage.mixed_molecule_get(ordered_mol_dict)

        # Build out services
        submitted_services = []
        for idx, mol in mol_query["data"].items():
            tmp = services.initializer(self.json["meta"]["service"], storage, self.json["meta"], mol)
            submitted_services.append(tmp)

        # Figure out complete services
        service_hashes = [x.data["hash_index"] for x in submitted_services]
        found_hashes = storage.get_procedures({"hash_index": service_hashes}, projection={"hash_index": True})
        found_hashes = set(x["hash_index"] for x in found_hashes["data"])

        new_services = []
        complete_jobs = []
        for x in submitted_services:
            hash_index = x.data["hash_index"]

            if hash_index in found_hashes:
                complete_jobs.append(hash_index)
            else:
                new_services.append(x)

        # Add services to database
        ret = storage.add_services([service.get_json() for service in new_services])
        self.logger.info("QUEUE: Added {} services.\n".format(ret["meta"]["n_inserted"]))

        ret["data"] = {"submitted": ret["data"], "completed": list(complete_jobs), "queue": ret["meta"]["duplicates"]}
        ret["meta"]["duplicates"] = []
        ret["meta"]["errors"].extend(errors)

        # Return anything of interest
        # meta["success"] = True
        # meta["n_inserted"] = len(submitted)
        # meta["errors"] = []  # TODO
        # ret = {"meta": meta, "data": submitted}

        self.write(ret)


def build_queue(queue_socket, db_socket, logger=None, **kwargs):
    """Constructs a queue and nanny based off the incoming queue socket type.

    Parameters
    ----------
    queue_socket : object ("distributed.Client", "fireworks.LaunchPad")
        A object wrapper for different queue types
    db_socket : DBSocket
        A socket to the underlying database
    logger : logging.Logger, Optional. Default: None
        Logger to report to
    **kwargs
        Additional kwargs for the QueueNanny

    Returns
    -------
    ret : (Nanny, Scheduler)
        Returns a valid Nanny and Scheduler for the selected computational queue

    """

    queue_type = type(queue_socket).__module__ + "." + type(queue_socket).__name__

    if queue_type == "distributed.client.Client":
        try:
            import dask.distributed
        except ImportError:
            raise ImportError(
                "Dask.distributed not installed, please install dask.distributed for the dask queue client.")

        from . import dask_handler

        adapter = dask_handler.DaskAdapter(queue_socket)

    elif queue_type == "fireworks.core.launchpad.LaunchPad":
        try:
            import fireworks
        except ImportError:
            raise ImportError("Fireworks not installed, please install fireworks for the fireworks queue client.")

        from . import fireworks_handler

        adapter = fireworks_handler.FireworksAdapter(queue_socket)

    else:
        raise KeyError("Queue type '{}' not understood".format(queue_type))

    nanny = QueueNanny(adapter, db_socket, logger=logger, **kwargs)
    queue = QueueScheduler
    service = ServiceScheduler

    return nanny, queue, service
