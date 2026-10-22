FROM scratch
COPY cache-worker /cache-worker
USER 65532:65532
ENTRYPOINT ["/cache-worker"]
