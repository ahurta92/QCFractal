"""
Schedulers and Nanny's for Fireworks
"""

class FireworksScheduler(tornado.web.RequestHandler):
    """
    Takes in a data packet the contains the molecule_hash, modelchem and options objects.
    """

    def initialize(self, **objects):
        self.objects = objects

        if "logger" in list(self.objects):
            self.logger = self.objects["logger"]
        else:
            self.logger = logging.getLogger('Scheduler')

    def post(self):
        # Fireworks
        import fireworks

        # Decode the data
        data = json.loads(self.request.body.decode('utf-8'))
        header = self.request.headers
        # _check_auth(self.objects, self.request.headers)

        # Grab objects
        self.objects["mongod_socket"].set_project(header["project"])
        lpad = self.objects["queue_socket"]
        queue_nanny = self.objects["queue_nanny"]

        tasks, program = _unpack_tasks(data, self.objects["mongod_socket"], self.logger)

        # Submit
        ret = {}
        ret["error"] = []
        ret["Nanny ID"] = []
        for task in tasks:
            if "internal_error" in list(task):
                ret["error"].append(task["internal_error"])
                continue
            fw = fireworks.Firework(
                fireworks.PyTask(func="dqm_compute.run_psi4", args=[task], stored_data_varname="results"))
            launches = lpad.add_wf(fw)
            fws_id = list(launches.values())[0]

            ret["Nanny ID"].append(self.objects["queue_nanny"].add_future(fws_id))

        # Return anything of interest
        ret["success"] = True
        self.write(json.dumps(ret))

    def get(self):

        header = self.request.headers
        # _check_auth(self.objects, self.request.headers)

        self.objects["mongod_socket"].set_project(header["project"])
        queue_nanny = self.objects["queue_nanny"]
        ret = {}
        ret["queue"] = list(queue_nanny.queue)
        ret["error"] = queue_nanny.errors
        self.write(json.dumps(ret))


class FireworksNanny(object):
    """
    This object can add to the Dask queue and watches for finished jobs. Jobs that are finished
    are automatically posted to the associated MongoDB and removed from the queue.
    """

    def __init__(self, queue_socket, mongod_socket, logger=None):

        self.queue_socket = queue_socket
        self.mongod_socket = mongod_socket
        self.queue = []
        self.errors = []

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('FireworksNanny')

    def add_future(self, future):
        self.queue.append(future)  # Should be unique via fireworks
        self.logger.info("MONGO ADD: FUTURE %s" % future)
        return future

    def update(self):
        # Fireworks
        import fireworks

        # Find completed projects
        fireworks_db = self.mongod_socket.client.fireworks
        cursor = fireworks_db.launches.find({
            "fw_id": {
                "$in": self.queue
            },
            "state": "COMPLETED"
        }, {"action.stored_data.results": True,
            "_id": False,
            "fw_id": True})

        for data in cursor:

            try:
                result_page = data["action"]["stored_data"]["results"]
                if not result_page["success"]:
                    raise ValueError("Computation (%s, %s) did not complete successfully!:\n%s\n" %
                                     (result_page["molecule_hash"], result_page["modelchem"], result_page["error"]))

                res = self.mongod_socket.add_page(result_page)
                self.logger.info("MONGO ADD: (%s, %s) - %s" % (result_page["molecule_hash"], result_page["modelchem"],
                                                               str(res)))

            except Exception as e:
                ename = str(type(e).__name__) + ":" + str(e)
                msg = "".join(traceback.format_tb(e.__traceback__))
                msg += str(type(e).__name__) + ":" + str(e)
                self.errors.append(msg)
                self.logger.info("MONGO ADD: ERROR\n%s" % msg)

            self.queue.remove(data["fw_id"])