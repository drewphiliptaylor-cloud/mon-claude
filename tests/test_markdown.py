"""Le rendu Markdown de l'interface (JavaScript) testé avec JavaScriptCore, présent sur tout Mac."""
import re
import subprocess
from pathlib import Path

import pytest

JSC = Path("/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc")
RACINE = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not JSC.exists(), reason="JavaScriptCore absent (pas un Mac)")
def test_markdown_sur_et_complet(tmp_path):
    source = (RACINE / "web/js/outils.js").read_text(encoding="utf-8")
    source = re.sub(r"^export ", "", source, flags=re.M)
    script = tmp_path / "md.js"
    script.write_text(source + "\n" + (RACINE / "tests/markdown_cas.js").read_text(encoding="utf-8"), encoding="utf-8")
    sortie = subprocess.run([str(JSC), str(script)], capture_output=True, text=True, timeout=30)
    assert sortie.stdout.strip().endswith("OK 7"), sortie.stdout + sortie.stderr
