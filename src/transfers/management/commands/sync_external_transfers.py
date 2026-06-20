from django.core.management.base import BaseCommand
from transfers.services import ElixirPZService


class Command(BaseCommand):
    help = 'Synchronizuje przelewy zewnętrzne (wychodzące i przychodzące) z systemem Elixir PZ'

    def handle(self, *args, **options):
        self.stdout.write("Rozpoczynanie synchronizacji przelewów z Elixir PZ...")
        try:
            ElixirPZService.sync_transfers()
            self.stdout.write(self.style.SUCCESS("Synchronizacja zakończona pomyślnie."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Wystąpił błąd podczas synchronizacji: {str(e)}"))
