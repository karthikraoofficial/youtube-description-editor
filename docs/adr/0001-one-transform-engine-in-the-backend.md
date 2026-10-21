# One transform engine, in the backend

Previews, review diffs and the descriptions actually written all come from the same Python `transforms` module. The React frontend never computes a description; it only renders what the backend returns. Duplicating the logic in TypeScript would make live previews slightly faster. But any drift between the two copies would mean writing something other than what the owner reviewed, which is the one thing this app must never do.
