"""
Contains testing infrastructure for QCFractal
"""

import pytest
import threading
import pkgutil
from contextlib import contextmanager
from tornado.ioloop import IOLoop
from .server import FractalServer
from .db_sockets import db_socket_factory


_server_port = 8888
test_server_address = "http://localhost:" + str(_server_port) + "/"


### Addon testing capabilities

def _plugin_import(plug):
    plug_spec = pkgutil.find_loader(plug)
    if plug_spec is None:
        return False
    else:
        return True

_import_message = "Not detecting module {}. Install package if necessary and add to envvar PYTHONPATH"

# Add a number of module testing options
using_fireworks = pytest.mark.skipif(_plugin_import('fireworks') is False, reason=_import_message.format('fireworks'))
using_dask = pytest.mark.skipif(_plugin_import('dask.distributed') is False, reason=_import_message.format('dask.distributed'))
using_psi4 = pytest.mark.skipif(_plugin_import('psi4') is False, reason=_import_message.format('psi4'))
using_rdkit = pytest.mark.skipif(_plugin_import('rdkit') is False, reason=_import_message.format('rdkit'))

### Server testing mechanics

@contextmanager
def pristine_loop():
    """
    Builds a clean IOLoop for using as a background request.
    Courtesy of Dask Distributed
    """
    IOLoop.clear_instance()
    IOLoop.clear_current()
    loop = IOLoop()
    loop.make_current()
    assert IOLoop.current() is loop

    try:
        yield loop
    finally:
        try:
            loop.close(all_fds=True)
        except ValueError:
            pass
        IOLoop.clear_instance()
        IOLoop.clear_current()

    db_name = "dqm_local_values_test"


@pytest.fixture(scope="module")
def test_server(request):
    """
    Builds a server instance with the event loop running in a thread.
    """

    db_name = "dqm_local_server_test"

    with pristine_loop() as loop:
        # Clean and re-init the databse, manually handle IOLoop (no start/stop needed)
        server = FractalServer(port=_server_port, db_project_name=db_name, io_loop=loop)
        server.db.client.drop_database(server.db._project_name)
        server.db.init_database()

        # Add the IOloop to a thread daemon
        thread = threading.Thread(target=loop.start, name="test IOLoop")
        thread.daemon = True
        thread.start()
        loop_started = threading.Event()
        loop.add_callback(loop_started.set)
        loop_started.wait()

        # Yield the server instance
        yield server

        # Cleanup
        loop.add_callback(loop.stop)
        thread.join(timeout=5)

@pytest.fixture(scope="module")
def test_database(request):
    db_name = "dqm_local_database_test"

    db = db_socket_factory("127.0.0.1", 27017, db_name)
    db.client.drop_database(db._project_name)
    db.init_database()

    yield db

    db.client.drop_database(db._project_name)
