from enum import Enum
from typing import List, Union, Optional, Dict, Any, Set, Iterable

from pydantic import BaseModel, Extra, validator, constr, Field
from typing_extensions import Literal

from qcportal.base_models import ProjURLParameters
from qcportal.molecules import Molecule
from qcportal.record_models import BaseRecord, RecordAddBodyBase, RecordQueryFilters
from qcportal.singlepoint.record_models import (
    QCSpecification,
    SinglepointRecord,
)


class BSSECorrectionEnum(str, Enum):
    none = "none"
    cp = "cp"


class ManybodyKeywords(BaseModel):
    class Config:
        extra = Extra.forbid

    max_nbody: Optional[int] = None
    bsse_correction: BSSECorrectionEnum

    @validator("max_nbody")
    def check_max_nbody(cls, v):
        if v is not None and v <= 0:
            raise ValueError("max_nbody must be None or > 0")
        return v


class ManybodySpecification(BaseModel):
    class Config:
        extra = Extra.forbid

    program: constr(to_lower=True) = "manybody"
    singlepoint_specification: QCSpecification
    keywords: ManybodyKeywords


class ManybodyAddBody(RecordAddBodyBase):
    specification: ManybodySpecification
    initial_molecules: List[Union[int, Molecule]]


class ManybodyQueryFilters(RecordQueryFilters):
    program: Optional[List[str]] = None
    qc_program: Optional[List[constr(to_lower=True)]] = None
    qc_method: Optional[List[constr(to_lower=True)]] = None
    qc_basis: Optional[List[Optional[constr(to_lower=True)]]] = None
    initial_molecule_id: Optional[List[int]] = None


class ManybodyCluster(BaseModel):
    class Config:
        extra = Extra.forbid

    molecule_id: int
    fragments: List[int]
    basis: List[int]
    degeneracy: int
    singlepoint_id: Optional[int]

    molecule: Optional[Molecule] = None
    singlepoint_record: Optional[SinglepointRecord]


class ManybodyRecord(BaseRecord):

    record_type: Literal["manybody"] = "manybody"
    specification: ManybodySpecification
    results: Optional[Dict[str, Any]]

    initial_molecule_id: int

    ######################################################
    # Fields not always included when fetching the record
    ######################################################
    initial_molecule_: Optional[Molecule] = Field(None, alias="initial_molecule")
    clusters_: Optional[List[ManybodyCluster]] = Field(None, alias="clusters")

    @staticmethod
    def transform_includes(includes: Optional[Iterable[str]]) -> Optional[Set[str]]:

        if includes is None:
            return None

        ret = BaseRecord.transform_includes(includes)

        if "initial_molecule" in includes:
            ret.add("initial_molecule")
        if "clusters" in includes:
            ret |= {"clusters.*", "clusters.singlepoint_record"}

        return ret

    def propagate_client(self, client):
        BaseRecord.propagate_client(self, client)

        if self.clusters_ is not None:
            for mb in self.clusters_:
                if mb.singlepoint_record:
                    mb.singlepoint_record.propagate_client(self._client)

    def _fetch_initial_molecule(self):
        self._assert_online()
        self.initial_molecule_ = self._client.get_molecules([self.initial_molecule_id])[0]

    def _fetch_clusters(self):
        self._assert_online()
        url_params = {"include": ["*", "molecule", "singlepoint_record"]}

        self.clusters_ = self._client._auto_request(
            "get",
            f"v1/records/manybody/{self.id}/clusters",
            None,
            ProjURLParameters,
            List[ManybodyCluster],
            None,
            url_params,
        )

        self.propagate_client(self._client)

    @property
    def initial_molecule(self) -> Molecule:
        if self.initial_molecule_ is None:
            self._fetch_initial_molecule()
        return self.initial_molecule_

    @property
    def clusters(self) -> List[ManybodyCluster]:
        if self.clusters_ is None:
            self._fetch_clusters()
        return self.clusters_
