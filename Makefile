.PHONY: test demo demo-two-voice clean
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	@command -v node >/dev/null && node --test docs/interactive-demo/engine.test.js || echo "node not found: skipping JavaScript rule tests"

demo:
	PYTHONPATH=src python3 -m arabic_tts_pipeline run --input examples/sample_entries.csv

demo-two-voice:
	PYTHONPATH=src python3 -m arabic_tts_pipeline two-voice-demo

clean:
	python3 -c "import shutil; shutil.rmtree('artifacts', ignore_errors=True)"

