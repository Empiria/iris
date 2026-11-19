# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

# Local development image for the Iris app server. Built and run by the justfile
# (`just build`, `just up`) under rootless podman.
#
# Local use only. The uplink key below is a fixed, well-known value, so this
# image must never be deployed and its port must never be published beyond
# loopback (`just up` binds 127.0.0.1).

# Java 21 matches the host JDK; jammy gives Python 3.10, matching the
# python310-minimal server spec and Anvil's pre-3.10 syntax constraint.
# The digest pins the multi-arch index of the 21-jre-jammy tag as it was on
# 2026-11-18. To update it, run
# `skopeo inspect --raw docker://docker.io/library/eclipse-temurin:21-jre-jammy | sha256sum`.
FROM docker.io/library/eclipse-temurin:21-jre-jammy@sha256:dff6eb46527bd293a3c06bbbe9e64e8c9f91f01905b5abbdad31761c03059d2c

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
#
# The JAR is checked against the sha256 below, so a changed download fails the
# build. When `anvil-app-server` is bumped, build once, copy the hash the
# failed check prints, and update the value.
ARG APP_SERVER_JAR_SHA256=7fc43b11ddc846d43b8ba17b0926954f26b36f2c42e47398251ba55d8954d67f
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -q anvil-app-server==1.17.0 -r /tmp/requirements.txt \
 && jar="$(python3 -c 'import anvil_app_server as a; print(a.find_or_download_app_server())' 2>/dev/null | tail -n 1)" \
 && actual="$(sha256sum "${jar}" | cut -d' ' -f1)" \
 && if [ "${actual}" != "${APP_SERVER_JAR_SHA256}" ]; then \
      echo "app-server JAR sha256 is ${actual}, expected ${APP_SERVER_JAR_SHA256}" >&2; exit 1; \
    fi

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

# The app's port inside the container. It is never the host port: `just up` picks a
# free loopback port, publishes it (-p 127.0.0.1:<port>:3030), passes
# --origin http://localhost:<port>, and records the URL in .anvil/stack-url.
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
