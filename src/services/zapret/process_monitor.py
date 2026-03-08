from src.services.windows.tasks import get_process_path, is_process_running, kill_process

class WinwsMonitor:
    def is_running(self) -> bool:
        return is_process_running('winws.exe')

    def kill(self) -> bool:
        return kill_process('winws.exe')

    def get_path(self) -> str:
        return get_process_path('winws')