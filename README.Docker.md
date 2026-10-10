### Building and running your application

When you're ready, start your application by running:
`docker compose up --build`.

Your application will be available at http://localhost:8000.

### Running the Gradio interface locally

From the project directory, activate the project environment and run:

```powershell
python gui.py
```

Then open http://127.0.0.1:7860. Attach the review process, review policy, and
target files, enter the requirement and required fields, and select `Start
review`. The interface pauses when the plan or a record needs human input. The
final result includes the generated DOCX report for download.

### Deploying your application to the cloud

First, build your image, e.g.: `docker build -t myapp .`.
If your cloud uses a different CPU architecture than your development
machine (e.g., you are on a Mac M1 and your cloud provider is amd64),
you'll want to build the image for that platform, e.g.:
`docker build --platform=linux/amd64 -t myapp .`.

Then, push it to your registry, e.g. `docker push myregistry.com/myapp`.

Consult Docker's [getting started](https://docs.docker.com/go/get-started-sharing/)
docs for more detail on building and pushing.

### References
* [Docker's Python guide](https://docs.docker.com/language/python/)