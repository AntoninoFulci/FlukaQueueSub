from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass


@dataclass
class JobInfo:
    input_file: str
    iteration: int
    fluka_path: str
    custom_exe: str | None


class QueueBackend(ABC):

    @abstractmethod
    def add_args(self, parser: ArgumentParser) -> None:
        """Aggiunge gli argomenti specifici del backend al subparser."""

    @abstractmethod
    def validate(self, args: Namespace) -> None:
        """Valida gli argomenti. Lancia ValueError se non validi."""

    @abstractmethod
    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str | None:
        """Genera lo script di job. Restituisce il path o None (es. Task Spooler)."""

    @abstractmethod
    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        """Invia il job. Restituisce una stringa descrittiva (job ID, ecc.)."""

    @abstractmethod
    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list[str]]:
        """Restituisce le righe specifiche del backend per la tabella di riepilogo."""
