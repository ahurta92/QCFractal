import atexit
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import psycopg2

from .config import FractalConfig
from .util import find_port


def _psql_return(data):
    """

    Finds the data line as show below:
    >>> _psql_return('''
     port
    ------
     5432
     2345
    (1 row)
    ''')
    ['5432', '2345']

    """
    return [x.strip() for x in data.splitlines()[2:-1]]


def _run(commands, quiet=True, logger=print):
    # proc = subprocess.run(commands, stdout=subprocess.PIPE)
    proc = subprocess.run(commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rcode = proc.returncode
    stdout = proc.stdout.decode()
    if not quiet:
        logger(stdout)

    return (rcode, stdout)


class PostgresHarness:
    def __init__(self, config, quiet=True, logger=print):
        self.config = config
        self.quiet = quiet
        self.logger = logger

    def database_uri(self):
        return self.config.database_uri(safe=False, database="")

    def connect(self, database=None):

        return psycopg2.connect(database=database,
                                user=self.config.database.username,
                                host=self.config.database.host,
                                port=self.config.database.port)

    def is_alive(self, database=None):

        try:
            self.connect(database=database)
            return True
        except psycopg2._psycopg.OperationalError:
            return False

    def command(self, cmd):
        if not self.quiet:
            logger(f"pqsl command: {cmd}")
        psql_cmd = [shutil.which("psql"), "-p", str(self.config.database.port), "-c"]
        return _run(psql_cmd + [cmd], logger=self.logger, quiet=self.quiet)

    def create_database(self, database_name):

        conn = self.connect()
        conn.autocommit = True

        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{database_name}'")
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f"CREATE DATABASE {database_name}")

        return self.is_alive(database=database_name)

    def shutdown(self):
        ret = _run([
            shutil.which("pg_ctl"),
            "-D", str(self.config.database_path),
            "stop"],
            logger=self.logger, quiet=self.quiet) # yapf: disable
        return ret

    def initialize(self):

        if not self.quiet:
            logger("Initializing the database:")

        # Initialize the database
        init_code, init_stdout = _run([shutil.which("initdb"), "-D", self.config.database_path],
                                      logger=self.logger,
                                      quiet=self.quiet)
        if "Success." not in init_stdout:
            raise ValueError(init_stdout)

        # Change any configurations
        psql_conf_file = (self.config.database_path / "postgresql.conf")
        psql_conf = psql_conf_file.read_text()
        if self.config.database.port != 5432:
            assert "#port = 5432" in psql_conf
            psql_conf = psql_conf.replace("#port = 5432", f"port = {self.config.database.port}")

            psql_conf_file.write_text(psql_conf)

        # Startup the server
        start_code, start_stdout = _run([
            shutil.which("pg_ctl"),
            "-D", str(self.config.database_path),
            "-l", str(self.config.base_path / self.config.database.logfile),
            "start"],
            logger=self.logger, quiet=self.quiet) # yapf: disable
        if "server started" not in start_stdout:
            raise ValueError(start_stdout)

        # Create teh user and database
        if not self.quiet:
            self.logger(f"Building user information.")
        ret = _run([shutil.which("createdb"), "-p", str(self.config.database.port)])

        success = self.create_database(self.config.database.default_database)

        if success is False:
            self.shutdown()
            raise ValueError("Database created successfully, but could not connect. Shutting down postgres.")


class TemporaryPostgres:
    def __init__(self, database_name: Optional[str] = None, tmpdir: Optional[str] = None, quiet=True, logger=print):
        """A PostgreSQL instance run in a temporary folder.

        ! Warning ! All data is lost when the server is shutdown.
        """

        self._active = True

        if not tmpdir:
            self._db_tmpdir = tempfile.TemporaryDirectory()
        else:
            self._db_tmpdir = tmpdir

        self.quiet = quiet
        self.logger = logger

        config_data = {"port": find_port(), "directory": self._db_tmpdir.name}
        if database_name:
            config_data["default_database"] = database_name
        self.config = FractalConfig(database=config_data)
        self.psql = PostgresHarness(self.config)
        self.psql.initialize()

        atexit.register(self.stop)

    def __del__(self):
        """
        Cleans up the TemporaryPostgres instance on delete.
        """

        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def database_uri(self, safe=True, database=None):
        return self.config.database_uri(safe=safe, database=database)

    def stop(self) -> None:
        """
        Shuts down the Snowflake instance. This instance is not recoverable after a stop call.
        """

        if not self._active:
            return

        self.psql.shutdown()

        # Closed down
        self._active = False
        atexit.unregister(self.stop)


# createuser [-p 5433] --superuser postgres
# psql [-p 5433] -c "create database qcarchivedb;" -U postgres
# psql [-p 5433] -c "create user qcarchive with password 'mypass';" -U postgres
# psql [-p 5433] -c "grant all privileges on database qcarchivedb to qcarchive;" -U postgres
