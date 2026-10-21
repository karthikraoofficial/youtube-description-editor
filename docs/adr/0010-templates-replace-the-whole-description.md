# Templates replace the whole description; {description} keeps the old text

A Template's result becomes the entire new description. That's the simplest meaning, and it's the only one that also lets a Template reorder or wrap the existing text. To keep the existing text, a Template must include the `{description}` variable. We considered "template = text appended to the description", but rejected it because Append to Description already does that. When `{description}` is missing, the Edit builder warns that every description will be replaced; the backend decides this, not the UI.

Template syntax is deliberately strict:
- `{{` and `}}` are literal braces, and a single `{` or `}` is an error.
- Spaces inside braces are allowed.
- Values are inserted literally, in one pass.

`{publish_date}` is the UTC calendar date, so the same Template gives the same text on any computer.

Saved Runs record the Template, so changing any of this later would change what old Runs mean.
