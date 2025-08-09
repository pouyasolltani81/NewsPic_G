# core/management/commands/initializedd.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils.termcolors import make_style

class Command(BaseCommand):
    help = '🔧 Runs full initialization: migrations for UserModel & AuthModel, then global migrate, then generates swagger.'

    def handle(self, *args, **kwargs):
        success = make_style(fg='green', opts=('bold',))
        warn = make_style(fg='yellow')
        error = make_style(fg='red', opts=('bold',))

        steps = [
            ("📦 Making migrations for UserModel", ('makemigrations', ['UserModel'])),
            ("🧱 Migrating UserModel", ('migrate', ['UserModel'])),
            ("📦 Making migrations for AuthModel", ('makemigrations', ['AuthModel'])),
            ("🧱 Migrating AuthModel", ('migrate', ['AuthModel'])),
            ("📦 Running global makemigrations", ('makemigrations', [])),
            ("🧱 Running global migrate", ('migrate', [])),
            ("📜 Generating Swagger YAML", ('spectacular', ['--color', '--file=swagger.yml']))
        ]

        for msg, (cmd, args) in steps:
            self.stdout.write(warn(f"\n{msg}..."))
            try:
                call_command(cmd, *args)
            except Exception as e:
                self.stdout.write(error(f"❌ Error during `{cmd}`: {e}"))
                break
        else:
            self.stdout.write(success("\n✅ All steps completed successfully."))
