FROM ruby:3.4-slim

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential libpq-dev libyaml-dev git python3 python3-requests python3-pandas python3-dotenv && \
    rm -rf /var/lib/apt/lists/*

ENV BUNDLE_PATH=/usr/local/bundle

COPY apps/backend/rails/Gemfile apps/backend/rails/Gemfile.lock /app/
RUN bundle install
COPY apps/backend/rails/ /app/

WORKDIR /opt/hackeurope
COPY ml/ ./ml/
COPY src/ ./src/
COPY lib/ ./lib/

WORKDIR /app
ENV SCHED_HOOK_ROOT=/opt/hackeurope
ENV SCHED_HOOK_PYTHON=python3
RUN mkdir -p /app/log /app/tmp/pids /app/tmp/cache && \
    touch /app/log/development.log && \
    chgrp -R 0 /app /opt/hackeurope && \
    chmod -R g=u /app /opt/hackeurope

CMD ["bash", "-lc", "bundle exec rails server -b 0.0.0.0 -p 3001"]
