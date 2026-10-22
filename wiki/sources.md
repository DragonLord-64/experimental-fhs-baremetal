# Source map

- Initial upstream: `https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal.git`, development commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
- [Environment plan](../docs/test-environment-plan.md): user discussion on 2026-10-21 plus local read-only inspection; includes history import limitations.
- [Monitoring README](../monitoring/README.md): deployment instructions for Prometheus, Telegraf, Elasticsearch, and Kibana.
- [Telemetry samples](../monitoring/example_output): existing node, FHS, and switch samples; suitability for replay remains unverified.
- [GitLab CI](../.gitlab-ci.yml): existing lint and documentation configuration; no role-test execution observed in this file.
- [Role test script](../scripts/molecule-test-all.sh): references a collection directory absent in the inspected checkout.
- DragonMind `AGENTS.md` and `README.md`: organizational inspiration for concise linked notes, provenance, and distinct plans and events; its unrelated automation is not adopted here.
