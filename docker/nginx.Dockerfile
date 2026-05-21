# syntax=docker/dockerfile:1.7
#
# nginx 1.27 with ngx_brotli built as dynamic modules.
# The official nginx image doesn't ship brotli, so stage 1 compiles the
# module against the same nginx source. Stage 2 is just the official image
# + the .so files + our config.
#
# We use the Debian-based nginx (not -alpine) because the apk repos require
# pre-existing TLS trust which breaks behind TLS-inspecting proxies. Same
# reasoning as the frontend Dockerfile.

ARG NGINX_VERSION=1.27.3

FROM nginx:${NGINX_VERSION} AS builder
ARG NGINX_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional: trust additional CAs (corporate TLS-inspecting proxies, etc).
COPY docker/extra-cas/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libpcre3-dev \
        libssl-dev \
        zlib1g-dev \
        cmake \
        wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN wget -qO nginx.tar.gz "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" \
    && tar -xzf nginx.tar.gz \
    && git clone --recurse-submodules -j8 --depth 1 https://github.com/google/ngx_brotli.git

# Compile the brotli C library (ngx_brotli links statically against it).
WORKDIR /src/ngx_brotli/deps/brotli
RUN mkdir -p out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF .. \
    && cmake --build . --config Release --target brotlienc brotlidec brotlicommon -j"$(nproc)"

WORKDIR /src/nginx-${NGINX_VERSION}
RUN ./configure --with-compat --add-dynamic-module=/src/ngx_brotli \
    && make -j"$(nproc)" modules \
    && mkdir -p /modules \
    && cp objs/ngx_http_brotli_filter_module.so /modules/ \
    && cp objs/ngx_http_brotli_static_module.so /modules/


FROM nginx:${NGINX_VERSION} AS runtime

COPY --from=builder /modules/ngx_http_brotli_filter_module.so /etc/nginx/modules/
COPY --from=builder /modules/ngx_http_brotli_static_module.so /etc/nginx/modules/
COPY docker/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
