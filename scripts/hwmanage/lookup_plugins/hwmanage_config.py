"""Read central controller configuration before inventory or playbook variables."""
from pathlib import Path
import sys
from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError

APP = Path(__file__).resolve().parents[1]


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        sys.path.insert(0, str(APP))
        from hwmanage_lib.settings import load, environment
        from hwmanage_lib.common import Error
        try:
            source, values = load(terms[0] if terms and terms[0] else None)
            password_file = values['credentials']['vault_password_file']
            if password_file and Path(password_file).is_file():
                from ansible.cli import CLI
                secrets = CLI.setup_vault_secrets(self._loader, vault_ids=[],
                    vault_password_files=[password_file], auto_prompt=False, initialize_context=False)
                self._loader.set_vault_secrets(secrets)
            mode = kwargs.get('mode', 'config')
            if mode == 'environment':
                return [environment(source, values)]
            if mode != 'config':
                raise ValueError('Unknown lookup mode')
            return [values]
        except Exception as error:
            # Credential/API values must never become inventory parse diagnostics.
            raise AnsibleError(str(error) if isinstance(error, Error) else 'Unable to load hwmanage controller configuration ('+type(error).__name__+')') from None
