# TextBook Exchange Demo

## Purpose
A minimal textbook exchange app demonstrating agentic development. Users can browse listings, sign up with username/password, and post textbooks for sale. Inspired by the MDN Express Library tutorial - simple, educational, functional.

## Constraints
- Keep it minimal - no unnecessary features
- Basic username/password auth (bcrypt for hashing)
- No email verification, no OAuth, no password reset
- Server-rendered views with Handlebars - no frontend framework
- HTMX for seamless page updates (optional progressive enhancement)

## Deliverables
- Express app with Handlebars templates
- SQLite database with users and listings tables
- Basic auth (register/login/logout)
- Public listing browsing
- Authenticated listing creation
- Minimal CSS styling

## Tech Choices
- TypeScript, Node.js, Express
- SQLite via `better-sqlite3`
- Drizzle ORM for schema + queries
- `express-session` for sessions
- Handlebars for server-side rendering
- bcrypt for password hashing

---

## Work Plan

### 1) Project Setup
- Initialize package.json with scripts: `dev`, `build`, `start`, `typecheck`
- Add TypeScript config (strict mode)
- Add Drizzle config for SQLite

### 2) Database Schema
- Create users table: id, username (unique), password_hash, created_at
- Create listings table: id, title, author, isbn, price (cents), condition, description, seller_id (FK), created_at
- Set up Drizzle client and initial migration

### 3) Express App + Views
- Set up Express with Handlebars engine
- Create main layout template
- Add static file serving (public/)
- Configure session middleware

### 4) Authentication
- Register page + POST handler (hash password, create user)
- Login page + POST handler (verify password, set session)
- Logout route (destroy session)
- Auth middleware for protected routes

### 5) Listings Feature
- Home page: show all listings (public)
- Listing detail page (public)
- Create listing form + handler (auth required)
- My listings page (auth required)

### 6) Styling + Polish
- Add minimal CSS for readability
- Add navigation header
- Display flash messages for errors/success

---

## Acceptance Checklist
- [ ] App starts with `npm run dev` and serves pages
- [ ] User can register with username/password
- [ ] User can login and logout
- [ ] Passwords are hashed (not stored in plain text)
- [ ] Home page shows all listings (no auth required)
- [ ] Logged-in user can create a new listing
- [ ] Listing detail page shows seller info
- [ ] My Listings page shows only current user's listings
