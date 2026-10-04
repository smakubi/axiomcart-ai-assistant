import subprocess
import sys


def test_voice_functions_do_not_load_langgraph():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import api.voice.session, api.voice.speak, api.voice.transcribe; "
                "import sys; assert 'langgraph' not in sys.modules; "
                "assert 'langchain_openai' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
