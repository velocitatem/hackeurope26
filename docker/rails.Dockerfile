FROM ruby:3.4-slim

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential libpq-dev libyaml-dev git python3 python3-requests python3-pandas python3-dotenv && \
    rm -rf /var/lib/apt/lists/*

ENV BUNDLE_PATH=/usr/local/bundle

COPY apps/backend/rails/Gemfile apps/backend/rails/Gemfile.lock /app/
RUN bundle install

WORKDIR /opt/hackeurope
COPY ml/ ./ml/
COPY src/ ./src/
COPY lib/ ./lib/

WORKDIR /app
ENV SCHED_HOOK_ROOT=/opt/hackeurope
ENV SCHED_HOOK_PYTHON=python3

CMD ["bash", "-lc", "bundle exec rails server -b 0.0.0.0 -p 3001"]
