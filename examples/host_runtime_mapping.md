# Host Runtime Mapping

- runtime start -> `solaris.open_session(kind="runtime")`
- wake start -> `solaris.open_session(kind="interaction")`
- committed turn -> `solaris.ingest_events`
- wake end -> `solaris.close_session` + `solaris.run_editorial_review`
- runtime shutdown -> `solaris.close_session` + `solaris.run_editorial_review`
