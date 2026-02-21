FROM ruby:3.4-slim

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential libpq-dev libyaml-dev git && \
    rm -rf /var/lib/apt/lists/*

ENV BUNDLE_PATH=/usr/local/bundle

COPY apps/backend/rails/Gemfile apps/backend/rails/Gemfile.lock /app/
RUN bundle install

CMD ["bash", "-lc", "bundle exec rails server -b 0.0.0.0 -p 3001"]
