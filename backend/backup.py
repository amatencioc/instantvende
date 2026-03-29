"""Sistema de backups automáticos de la base de datos SQLite."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule


class BackupManager:
    """Gestiona la creación y limpieza de backups de la BD SQLite."""

    def __init__(
        self,
        db_path: str = "./instantvende.db",
        backup_dir: str = "./backups",
        max_backups: int = 10,
    ) -> None:
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups

    def create_backup(self) -> str:
        """Crea un backup timestamped usando la API nativa de SQLite.

        Usa sqlite3.Connection.backup() que es seguro incluso bajo carga.
        Devuelve la ruta del archivo de backup creado.
        """
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"instantvende_{timestamp}.db"

        source = sqlite3.connect(self.db_path)
        dest = sqlite3.connect(str(backup_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()

        return str(backup_path)

    def cleanup_old_backups(self) -> int:
        """Elimina los backups más antiguos conservando solo max_backups.

        Devuelve el número de archivos eliminados.
        """
        if not self.backup_dir.exists():
            return 0

        backups = sorted(self.backup_dir.glob("instantvende_*.db"))
        removed = 0
        while len(backups) > self.max_backups:
            backups.pop(0).unlink(missing_ok=True)
            removed += 1
        return removed


# ---------------------------------------------------------------------------
# Scheduler de backups periódicos
# ---------------------------------------------------------------------------

def start_backup_scheduler(
    db_path: str = "./instantvende.db",
    backup_dir: str = "./backups",
    interval_hours: int = 6,
    max_backups: int = 10,
) -> None:
    """Inicia el scheduler de backups usando la librería schedule.

    Diseñado para ejecutarse en un hilo daemon separado.
    """
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir, max_backups=max_backups)

    def _job() -> None:
        try:
            path = manager.create_backup()
            removed = manager.cleanup_old_backups()
            # Importamos el logger aquí para evitar importaciones circulares
            import logging
            log = logging.getLogger("instantvende")
            log.info("Backup automático creado", extra={"path": path, "removed": removed})
        except Exception as exc:
            import logging
            log = logging.getLogger("instantvende")
            log.error("Error en backup automático", extra={"error": str(exc)})

    schedule.every(interval_hours).hours.do(_job)

    while True:
        schedule.run_pending()
        time.sleep(60)
