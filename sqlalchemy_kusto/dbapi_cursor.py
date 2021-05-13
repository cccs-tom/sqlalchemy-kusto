from collections import namedtuple

from azure.kusto.data._models import KustoResultColumn

from sqlalchemy_kusto.utils import check_closed, check_result
from azure.kusto.data import KustoClient, ClientRequestProperties
from typing import Optional


CursorDescriptionRow = namedtuple(
        "CursorDescriptionRow",
        ["name", "type", "display_size", "internal_size", "precision", "scale", "null_ok"],
    )


class Cursor(object):
    """Connection cursor."""

    def __init__(
            self,
            kusto_client: KustoClient,
            database: str,
            properties: Optional[ClientRequestProperties] = None,
    ):
        self.kusto_client = kusto_client
        self.database = database
        self.properties = properties
        self.closed = False
        self.description = None
        self._results = None

    @property
    @check_result
    @check_closed
    def rowcount(self):
        # consume the iterator
        results = list(self._results)
        n = len(results)
        # self._results = iter(results)
        return n

    @check_closed
    def close(self):
        """Close the cursor."""
        self.closed = True

    @check_closed
    def execute(self, operation, parameters=None):
        query = apply_parameters(operation, parameters)
        server_response = self.kusto_client.execute(self.database, query, self.properties)
        rows = []
        for row in server_response.primary_results[0]:
            rows.append(tuple(row.to_list()))
        self._results = rows
        self.description = self._get_description_from_columns(server_response.primary_results[0].columns)
        return self

    @check_closed
    def executemany(self, operation, seq_of_parameters=None):
        raise NotImplementedError(
            "`executemany` is not supported, use `execute` instead"
        )

    @check_result
    @check_closed
    def fetchone(self):
        raise NotImplementedError(
            "`fetchone` is not supported, use `execute` instead"
        )

    @check_result
    @check_closed
    def fetchmany(self, size=None):
        if size is not None:
            raise NotImplementedError(
                "`fetchmany` is not supported, use `execute` instead"
            )
        return list(self._results)

    @check_result
    @check_closed
    def fetchall(self):
        """
        Fetch all (remaining) rows of a query result, returning them as a
        sequence of sequences (e.g. a list of tuples). Note that the cursor's
        arraysize attribute can affect the performance of this operation.
        """
        return list(self._results)

    @check_closed
    def setinputsizes(self, sizes):
        # not supported
        pass

    @check_closed
    def setoutputsizes(self, sizes):
        # not supported
        pass



    @staticmethod
    def _get_description_from_columns(columns: KustoResultColumn):
        return [
            CursorDescriptionRow(
                name=column.column_name,
                type=column.column_type,
                display_size=None,
                internal_size=None,
                precision=None,
                scale=None,
                null_ok=True,
            )
            for column in columns
        ]

    @check_closed
    def __iter__(self):
        return self

    @check_closed
    def __next__(self):
        return next(self._results)

    next = __next__


def apply_parameters(operation, parameters):
    if not parameters:
        return operation

    escaped_parameters = {key: escape(value) for key, value in parameters.items()}
    return operation % escaped_parameters


def escape(value):
    """
    Escape the parameter value.

    Note that bool is a subclass of int so order of statements matter.
    """

    if value == "*":
        return value
    elif isinstance(value, str):
        return "'{}'".format(value.replace("'", "''"))
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, (list, tuple)):
        return ", ".join(escape(element) for element in value)
