ARG BASE_IMAGE=ubuntu:26.04
FROM ${BASE_IMAGE}

ARG BOOTSTRAP_FAMILY
ARG OS_RELEASE_NAME=
ARG OS_RELEASE_ID=
ARG OS_RELEASE_PRETTY_NAME=
ARG OS_RELEASE_VERSION_CODENAME=
ARG OS_RELEASE_UBUNTU_CODENAME=
ARG INSTALL_URL=https://mwm.datallog.com/install.sh
ARG EXPECT_CONTAINER_ENGINE=
ARG TEST_NAME=unknown

ENV DEBIAN_FRONTEND=noninteractive
ENV DATALLOG_ALLOW_ROOT=1
ENV HOME=/root
ENV USER=root
ENV TEST_NAME=${TEST_NAME}
ENV EXPECT_CONTAINER_ENGINE=${EXPECT_CONTAINER_ENGINE}

COPY tests/install-smoke/bootstrap.sh /tmp/bootstrap.sh
COPY tests/install-smoke/assert-install.sh /tmp/assert-install.sh

RUN chmod +x /tmp/bootstrap.sh /tmp/assert-install.sh
RUN /tmp/bootstrap.sh

RUN bash -lc 'if [[ -n "${OS_RELEASE_ID}" ]]; then \
      printf '\''NAME="%s"\nID=%s\nPRETTY_NAME="%s"\nVERSION_CODENAME=%s\nUBUNTU_CODENAME=%s\n'\'' \
        "${OS_RELEASE_NAME}" \
        "${OS_RELEASE_ID}" \
        "${OS_RELEASE_PRETTY_NAME}" \
        "${OS_RELEASE_VERSION_CODENAME}" \
        "${OS_RELEASE_UBUNTU_CODENAME}" \
        > /etc/os-release; \
    fi'

RUN curl -SsLf "${INSTALL_URL}" | bash
RUN /tmp/assert-install.sh
