"""Generation-only roots: register the production ``repo`` models with firepact
WITHOUT modifying them.

``firestore_realtime`` is applied as a plain function (not a decorator on the
class), so ``repo.py`` carries no firepact import and firepact stays a dev/gen
-only dependency. ``firepact-gen --module examples.gen.realtime_app._fp_roots`` emits
every registered root into one ``firestore.ts``.

``guaranteed`` lists the fields present since each collection's first version
(read-required); everything added later stays read-optional, because a residual
document at an older version genuinely lacks it (FULL_TRANSITIVE safe). For
``User`` that is everything except ``plan`` (added in v1) and ``display_name``
(optional); for ``Chat`` (single version) it is every field.
"""

from firepact import firestore_realtime

from .repo import Chat, User

firestore_realtime(
    collection="users",
    id_field=None,
    guaranteed=["id", "created_at", "updated_at", "version", "handle"],
)(User)

firestore_realtime(
    collection="users/{userId}/chats",
    id_field=None,
    guaranteed=["id", "created_at", "updated_at", "version", "status", "messages"],
)(Chat)
