# URL Shortener

## Overview

A minimal fullstack URL shortener built with TypeScript, Express, Handlebars, and HTMX. Demonstrates the complete ClaudeSprint workflow from setup to tested, working application.

## Tech Stack

- **Language:** TypeScript
- **Backend:** Express
- **Templating:** Handlebars (express-handlebars)
- **Frontend:** HTMX (via npm)
- **Database:** JSON file
- **Testing:** Vitest
- **Architecture:** MVC

## Constraints

- Node.js 18+
- All dependencies via npm (no CDN)
- Must run with `npx tsx src/index.ts`
- Tests run with `npx vitest run`

## Deliverables

A working URL shortener that:
- Accepts a long URL and returns a shortened code
- Redirects short URLs to their original destination
- Persists URLs to a JSON file
- Has a clean HTMX-powered UI
- Includes unit and integration tests

## Project Structure

```
src/
├── controllers/
│   └── urlController.ts
├── models/
│   └── urlModel.ts
├── views/
│   ├── layouts/
│   │   └── main.handlebars
│   ├── home.handlebars
│   └── partials/
│       └── urlResult.handlebars
├── routes/
│   └── urlRoutes.ts
├── services/
│   └── urlService.ts
├── middleware/
│   └── errorHandler.ts
├── utils/
│   └── db.ts
├── app.ts
└── index.ts
data/
└── urls.json
tests/
├── urlService.test.ts
└── urlRoutes.test.ts
```

## Work Plan

### Issue 1: Project Setup and Express Configuration

Initialize the TypeScript project with Express and Handlebars.

**Tasks:**
- Initialize package.json with all dependencies
- Create tsconfig.json for TypeScript
- Set up Express app with Handlebars templating engine
- Create main layout template
- Serve HTMX from node_modules
- Create basic home route that renders

**Acceptance Criteria:**
- Running `npm install` installs all dependencies
- Running `npx tsx src/index.ts` starts server on port 3000
- Visiting `http://localhost:3000` shows a basic page with "URL Shortener" heading
- HTMX is loaded from local node_modules (check network tab)

---

### Issue 2: URL Shortening Backend

Implement the MVC backend for creating and resolving short URLs.

**Tasks:**
- Create `src/utils/db.ts` - JSON file read/write helpers
- Create `src/models/urlModel.ts` - URL type definition and data access
- Create `src/services/urlService.ts` - Business logic (create short URL, resolve code)
- Create `src/controllers/urlController.ts` - Request handlers
- Create `src/routes/urlRoutes.ts` - Route definitions
- Create `src/middleware/errorHandler.ts` - Global error handler
- Wire routes into Express app

**Acceptance Criteria:**
- POST `/api/shorten` with `{ "url": "https://example.com" }` returns `{ "code": "abc123", "shortUrl": "http://localhost:3000/abc123" }`
- GET `/abc123` redirects (302) to the original URL
- GET `/nonexistent` returns 404
- Invalid URLs return 400 with error message
- URLs persist in `data/urls.json` and survive server restart

---

### Issue 3: HTMX Frontend

Create the Handlebars views with HTMX for a dynamic UI.

**Tasks:**
- Update `src/views/home.handlebars` with URL input form
- Create `src/views/partials/urlResult.handlebars` for displaying shortened URL
- Add HTMX attributes to form for async submission
- Create controller endpoint that returns HTML partial
- Add basic CSS styling (inline or style tag)
- Show list of recently created URLs

**Acceptance Criteria:**
- Home page shows a form with URL input and submit button
- Submitting form does NOT reload page (HTMX handles it)
- Shortened URL appears below form after submission
- Shortened URL is clickable and opens in new tab
- Recently shortened URLs are listed on the page
- UI is clean and usable (basic styling applied)

---

### Issue 4: Tests

Add unit and integration tests with Vitest.

**Tasks:**
- Configure Vitest in package.json
- Create `tests/urlService.test.ts` - Unit tests for service layer
- Create `tests/urlRoutes.test.ts` - Integration tests for API endpoints
- Ensure tests use isolated test data (not production urls.json)

**Acceptance Criteria:**
- Running `npx vitest run` executes all tests
- Unit tests cover: URL validation, code generation, URL resolution
- Integration tests cover: POST /api/shorten, GET /:code redirect, 404 handling
- All tests pass
- Tests do not pollute production data
