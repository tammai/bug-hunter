# Edge inputs: a web UI in a browser

Use with the other lists when `/hunt --target <name> --browser` hunts a running server's UI. Read the component or template and the handler it calls first, then prove each suspect with one Playwright test run through `browser.py run`. Each line: what to do, and the bug it tends to find.

**How to try them:** write `bh-repro.spec.ts` and run it with `python3 "<PLUGIN>/scripts/browser.py" run --copy "<SCRATCH>/copy" --test bh-repro.spec.ts --base "$ACCEPT_BASE_URL"`.
- The test reaches the app through `page.goto('/<path>')`: the base comes from `ACCEPT_BASE_URL`, which is the proxy.
- A test logs in by reading `ACCEPT_ACCOUNT_<NAME>`, a header line like `X-Bug-Hunter-Account: bob`, and calling `page.setExtraHTTPHeaders`.
- The browser can reach only the proxy; a link or redirect to anywhere else fails.
- Assert what the user would see (a count, a text, a URL), not internals.

## Doing it twice
- **Double submit:** `dblclick` the submit button, or click it twice quickly. Look for two records, two charges or two emails where one was meant.
- **Back and forward after a write:** submit a form, then `page.goBack()` and `page.goForward()`, or reload the page the POST returned. Look for a second write, or stale data shown as current.
- **A stale tab:** open the record in two pages, change or delete it in one, then save the other. Look for a lost update, or a save of a deleted record that answers 200.
- **Two tabs editing one record:** edit the same field in two pages and save both. Look for the last write silently winning when the app claims to detect conflicts.

## What the user types
- **Long text:** 10,000 characters in a field. Look for truncation without a message, a layout that hides the save button, or a 500.
- **Right-to-left and mixed text:** Arabic or Hebrew, with numbers and Latin letters in one value. Look for the wrong order on save or reload, or cut-off characters.
- **Emoji and combining marks:** `👍🏽`, `é` written as `e` plus a combining accent. Look for counts and limits that split a character, or a mangled save.

## What the page shows
- **An empty list:** a fresh account with no records. Look for a crash, "undefined" in the page, or a spinner that never stops.
- **A huge list:** hundreds or thousands of records (create them first when writes are allowed). Look for a frozen page, missing pagination, or only the first page saved.

## Time and the network
- **A slow network:** delay responses with `page.route('**', r => setTimeout(() => r.continue(), 2000))`. Look for double actions, buttons that stay enabled, or responses applied in the wrong order.
- **Session expiry mid-form:** fill a form, drop the login (`page.setExtraHTTPHeaders({})` or clear cookies), then submit. Look for lost input, a silent failure that looks like success, or a redirect that discards the data.

## Without a mouse
- **Keyboard only:** reach and use the flow with `Tab`, `Enter` and `Space` alone. Look for controls that can't be focused, `Enter` submitting twice, or a dialog that can't be closed.
