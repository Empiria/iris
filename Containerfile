# Local development image for the Iris app server. Built and run by the justfile
# (`just build`, `just up`) under rootless podman.
#
# Local use only. The uplink key below is a fixed, well-known value, so this
# image must never be deployed and its port must never be published beyond
# loopback (`just up` binds 127.0.0.1).

# Java 21 matches the host JDK; jammy gives Python 3.10, matching the
# python310-minimal server spec and Anvil's pre-3.10 syntax constraint.
FROM docker.io/library/eclipse-temurin:21-jre-jammy

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# The built-in downlink runs the app's server_code in this image's Python, so any
# third-party package the server modules import must be installed here.
# requirements.txt is a copy of server_code/requirements.txt made by `just build`.
#
# The server JAR is not in the wheel. It is fetched on first launch into the
# root-owned package directory, which the unprivileged runtime user cannot write.
# So it is fetched here, as root, at build time: baked in, read-only and readable
# by the runtime user. This step needs outbound network access to the host that
# serves the JAR.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir anvil-app-server==1.17.0 -r /tmp/requirements.txt \
 && python3 -c "import anvil_app_server; anvil_app_server.find_or_download_app_server()"

# Embedded Postgres refuses to run as root. /data is created owned by the
# unprivileged user, and the empty named volume inherits that ownership when it
# is first mounted over /data.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /srv /data \
 && chown -R app:app /srv /data
USER app
WORKDIR /srv

# Dependency apps staged by `just build`. Each directory is named after its
# package_name so the app server finds it as a sibling of the app itself.
COPY --chown=app:app deps/ /srv/

EXPOSE 3030

# The app itself is bind-mounted at /srv/<package_name> by `just up`.
# Neither --app nor the --dep-id flags are listed here: `just up` appends them
# after the image name, the path from the app's package_name and the ids from
# `tools/anvil_deps.py --dep-id-args`, so they always come from anvil.yaml.
# After a package_name or dependency change in the IDE, recreate the container
# with `just fresh`.
# --auto-migrate creates the schema from anvil.yaml on the first boot against an
# empty volume. --ignore-invalid-schema keeps restarts safe: an index the local
# migrator can't build would otherwise crash every boot after the first.
ENTRYPOINT ["anvil-app-server", "--data-dir", "/data", "--auto-migrate", "--ignore-invalid-schema", "--uplink-key", "dev-uplink"]
