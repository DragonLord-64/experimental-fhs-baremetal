FROM scratch
COPY sender /sender
USER 65532:65532
ENTRYPOINT ["/sender"]
