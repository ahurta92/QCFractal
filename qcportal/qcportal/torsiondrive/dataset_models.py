from typing import Dict, Any, Union, Optional, List, Iterable, Tuple

from pydantic import BaseModel, Extra
from typing_extensions import Literal

from qcportal.dataset_models import BaseDataset
from qcportal.metadata_models import InsertMetadata
from qcportal.molecules import Molecule
from qcportal.torsiondrive.record_models import TorsiondriveRecord, TorsiondriveSpecification
from qcportal.utils import make_list


class TorsiondriveDatasetNewEntry(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str
    initial_molecules: List[Union[Molecule, int]]
    additional_keywords: Dict[str, Any] = {}
    additional_optimization_keywords: Dict[str, Any] = {}
    attributes: Dict[str, Any] = {}
    comment: Optional[str] = None


class TorsiondriveDatasetEntry(TorsiondriveDatasetNewEntry):
    initial_molecules: List[Molecule]


# Torsiondrive dataset specifications are just optimization specifications
# The torsiondrive keywords are stored in the entries ^^
class TorsiondriveDatasetSpecification(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str
    specification: TorsiondriveSpecification
    description: Optional[str] = None


class TorsiondriveDatasetRecordItem(BaseModel):
    class Config:
        extra = Extra.forbid

    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[TorsiondriveRecord]


class TorsiondriveDataset(BaseDataset):
    class _DataModel(BaseDataset._DataModel):
        dataset_type: Literal["torsiondrive"] = "torsiondrive"

        specifications: Dict[str, TorsiondriveDatasetSpecification] = {}
        entries: Dict[str, TorsiondriveDatasetEntry] = {}
        record_map: Dict[Tuple[str, str], TorsiondriveRecord] = {}

    raw_data: _DataModel

    # Needed by the base class
    _entry_type = TorsiondriveDatasetEntry
    _specification_type = TorsiondriveDatasetSpecification
    _record_item_type = TorsiondriveDatasetRecordItem
    _record_type = TorsiondriveRecord

    def add_specification(
        self, name: str, specification: TorsiondriveSpecification, description: Optional[str] = None
    ) -> InsertMetadata:

        payload = TorsiondriveDatasetSpecification(name=name, specification=specification, description=description)

        ret = self.client._auto_request(
            "post",
            f"v1/datasets/torsiondrive/{self.id}/specifications",
            List[TorsiondriveDatasetSpecification],
            None,
            InsertMetadata,
            [payload],
            None,
        )

        self._post_add_specification(name)
        return ret

    def add_entries(
        self, entries: Union[TorsiondriveDatasetNewEntry, Iterable[TorsiondriveDatasetNewEntry]]
    ) -> InsertMetadata:

        entries = make_list(entries)
        ret = self.client._auto_request(
            "post",
            f"v1/datasets/torsiondrive/{self.id}/entries/bulkCreate",
            List[TorsiondriveDatasetNewEntry],
            None,
            InsertMetadata,
            entries,
            None,
        )

        new_names = [x.name for x in entries]
        self._post_add_entries(new_names)
        return ret

    def add_entry(
        self,
        name: str,
        initial_molecules: List[Union[Molecule, int]],
        additional_keywords: Optional[Dict[str, Any]] = None,
        additional_optimization_keywords: Optional[Dict[str, Any]] = None,
        attributes: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ):

        ent = TorsiondriveDatasetNewEntry(
            name=name,
            initial_molecules=initial_molecules,
            additional_keywords=additional_keywords,
            additional_optimization_keywords=additional_optimization_keywords,
            attributes=attributes,
            comment=comment,
        )

        return self.add_entries(ent)
