# Milestone 6 – React Web UI

## Goals
- Implement a React UI that interacts with the FastAPI backend.
- Provide pages for dashboard, positions, orders, and basic monitoring.
- Incorporate client-side validation, error display, and logging hooks.

## Scope Mapping to Technical Spec
- Section 2 – Core Components (stocks-webapp)
- Section 4 – Directory Layout
- Section 9 – Development and Trading Best Practices (user-facing workflows)

## Tasks

### 1. React App Skeleton
- Initialize React app inside `services/stocks-webapp`.
- Configure `REACT_APP_API_URL` and `REACT_APP_CONTAINER_TYPE=stocks`.

### 2. Pages and Components
- `DashboardPage`:
  - High-level account value, open PnL, and recent activity.

- `OrdersPage`:
  - New order ticket form.
  - Order history table.

- `PositionsPage`:
  - Open positions table.
  - Basic filtering and sorting.

### 3. API Client and Error Handling
- Implement a small API client wrapper:
  - Centralizes base URL and headers.
  - Handles JSON parsing and error translation.

- Global error boundary:
  - Displays user-friendly messages.
  - Logs details to console (and optionally to backend later).

### 4. UI Tests
- Use Jest + React Testing Library:
  - Test rendering of pages.
  - Test validation behavior for order form.
  - Test that API calls are made correctly (mock fetch/axios).

## Checkpoint – Milestone 6

### Definition of Done
- Frontend can:
  - Fetch positions and orders from backend.
  - Place a simple market/limit order via UI.
- Basic error messages shown for failure cases.

### Test Plan
- Manual E2E test:
  - Start full stack.
  - Open `http://localhost:3001`.
  - Place a test paper order; confirm in:
    - UI
    - DB
    - IBKR TWS / Account.

### Planned Unit Tests
- `src/__tests__/DashboardPage.test.tsx`
- `src/__tests__/OrdersPage.test.tsx`
- `src/__tests__/PositionsPage.test.tsx`
- API client tests for success and failure paths.

---
