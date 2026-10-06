from typing import List, Optional
from app.models.case import Case
from app.schemas.case import CaseCreate
from app.repositories.case_repository import CaseRepository

class CaseService:
    @staticmethod
    def create_case(case_data: CaseCreate) -> Case:
        """
        Creates a new case and stores it in database.
        """
        new_case = Case(
            case_name=case_data.case_name,
            description=case_data.description
        )
        CaseRepository.insert(new_case)
        return new_case

    @staticmethod
    def get_all_cases() -> List[Case]:
        """
        Retrieves all cases from the database.
        """
        return CaseRepository.get_all()

    @staticmethod
    def get_case_by_id(case_id: str) -> Optional[Case]:
        """
        Retrieves a single case by its unique ID.
        """
        return CaseRepository.get_by_id(case_id)
