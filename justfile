venv := "venv"
python := venv / "bin/python"

[script]
[arg("force", short="f", long="force", value="true")] 
venv force="false":
    if [ -d "{{venv}}" ] && [ "{{force}}" != "true" ]; then exit 0; fi
    uv venv --clear --python 3.14 {{venv}}
    uv pip install --upgrade -r requirements.txt --python {{venv}}

[script]
dev: venv
    DRIP_BASE_URL=http://host.docker.internal:5001 DRIP_ENVIRONMENT=dev DRIP_DB_PATH=./drip.db {{python}} -m app

db-drop:
    rm drip.db
