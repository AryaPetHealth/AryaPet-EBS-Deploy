#!/bin/sh
# Runs once per container start, before the API/worker come up. Safe on every deploy
# (including redeploys with no new migrations) since `alembic upgrade head` is a no-op
# once the DB is already at head. Container fails to start if the migration fails,
# rather than serving traffic against a schema the code doesn't match.
set -e

alembic upgrade head

exec supervisord -c supervisord.conf
