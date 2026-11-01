.PHONY: test demo demo-two-voice clean
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

demo:
	PYTHONPATH=src python3 -m arabic_tts_pipeline run --input examples/sample_entries.csv

demo-two-voice:
	PYTHONPATH=src python3 -m arabic_tts_pipeline two-voice-demo

clean:
	python3 -c "import shutil; shutil.rmtree('artifacts', ignore_errors=True)"

