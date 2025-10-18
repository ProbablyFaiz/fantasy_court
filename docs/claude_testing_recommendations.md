## Modern Frontend Testing Philosophy

**The Testing Trophy:** Focus most effort on integration tests, fewer unit tests, some E2E tests. Avoid the "testing pyramid" - it's outdated.

**Core Principles:**
- **Test behavior, not implementation** - Don't test internal component state; test what users see/do
- **Confidence over coverage** - 80% coverage of critical paths > 100% coverage of trivial code
- **Fast feedback loops** - Tests should run in <1s for TDD-style development

## Frontend Testing Stack Deep Dive

### Vitest (Test Runner)
**Why not Jest?** Vitest is faster, has better TypeScript support, and shares Vite's config. It's Jest-compatible but modern.

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true, // No need to import describe/it/expect
  },
})
```

### Testing Library Approach
**Philosophy:** "The more your tests resemble the way your software is used, the more confidence they can give you."

**Key APIs:**
- `getByRole()` - Primary query (accessibility-focused)
- `getByText()` - For user-visible text
- `getByLabelText()` - For form inputs
- `queryBy*()` - When element might not exist
- `findBy*()` - For async elements

```typescript
// Good test - tests behavior
test('user can submit a form', async () => {
  render(<ContactForm />)

  await user.type(screen.getByLabelText(/email/i), 'test@example.com')
  await user.type(screen.getByLabelText(/message/i), 'Hello world')
  await user.click(screen.getByRole('button', { name: /submit/i }))

  expect(screen.getByText(/thank you/i)).toBeInTheDocument()
})

// Bad test - tests implementation
test('form state updates correctly', () => {
  const { getByTestId } = render(<ContactForm />)
  const component = getByTestId('contact-form')

  // Testing internal React state - brittle and useless
  expect(component.state.email).toBe('')
})
```

### MSW (Mock Service Worker)
**Why MSW?** Intercepts network requests at the service worker level - your app thinks it's making real API calls.

```typescript
// tests/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json([
      { id: 1, name: 'John' },
      { id: 2, name: 'Jane' },
    ])
  }),

  http.post('/api/users', async ({ request }) => {
    const user = await request.json()
    return HttpResponse.json({ id: 3, ...user }, { status: 201 })
  }),
]
```

### Modern Testing Patterns

**1. Container/Component Testing**
Test your route components - they exercise the full data flow:

```typescript
test('user list page loads and displays users', async () => {
  render(<UserListPage />)

  // Shows loading state
  expect(screen.getByText(/loading/i)).toBeInTheDocument()

  // Shows users after load
  expect(await screen.findByText('John')).toBeInTheDocument()
  expect(screen.getByText('Jane')).toBeInTheDocument()
})
```

**2. User Event Testing**
Always use `@testing-library/user-event` for interactions:

```typescript
// Good - simulates real user interaction
await user.click(button)
await user.type(input, 'text')
await user.selectOptions(select, 'option')

// Bad - doesn't trigger proper event chains
fireEvent.click(button)
```

**3. Async Testing**
Modern apps are async. Use `findBy*` and `waitFor`:

```typescript
test('search shows results', async () => {
  render(<SearchPage />)

  await user.type(screen.getByRole('searchbox'), 'react')

  // Wait for debounced search
  expect(await screen.findByText('React Documentation')).toBeInTheDocument()
})
```

## End-to-End Testing with Playwright

**Why Playwright?** Fast, reliable, great developer experience. Better than Cypress for modern apps.

**Key Features:**
- **Auto-wait** - No manual waits for elements
- **Multiple browsers** - Chrome, Firefox, Safari
- **Great debugging** - Time-travel debugging, trace viewer
- **Parallel execution** - Tests run in parallel by default

### Playwright Best Practices

**1. Page Object Model (Optional but Useful)**
```typescript
// pages/LoginPage.ts
export class LoginPage {
  constructor(private page: Page) {}

  async login(email: string, password: string) {
    await this.page.getByLabel('Email').fill(email)
    await this.page.getByLabel('Password').fill(password)
    await this.page.getByRole('button', { name: 'Sign in' }).click()
  }

  async expectLoggedIn() {
    await expect(this.page.getByText('Welcome')).toBeVisible()
  }
}
```

**2. Test Critical User Journeys**
```typescript
test('user can complete purchase flow', async ({ page }) => {
  await page.goto('/products')

  // Add to cart
  await page.getByRole('button', { name: 'Add to cart' }).first().click()
  await page.getByRole('link', { name: 'Cart' }).click()

  // Checkout
  await page.getByRole('button', { name: 'Checkout' }).click()
  await page.getByLabel('Email').fill('test@example.com')
  await page.getByLabel('Card number').fill('4242424242424242')
  await page.getByRole('button', { name: 'Complete order' }).click()

  // Verify success
  await expect(page.getByText('Order confirmed')).toBeVisible()
})
```

**3. API Testing in Playwright**
```typescript
test('API creates user correctly', async ({ request }) => {
  const response = await request.post('/api/users', {
    data: { name: 'John', email: 'john@example.com' }
  })

  expect(response.ok()).toBeTruthy()
  const user = await response.json()
  expect(user.name).toBe('John')
})
```

## Testing Strategy

**Frontend Unit Tests (20%)**
- Utility functions
- Custom hooks
- Complex components in isolation

**Frontend Integration Tests (60%)**
- Full page/feature testing
- API integration with MSW
- User workflows within a feature

**E2E Tests (20%)**
- Critical user journeys
- Cross-browser compatibility
- Performance/accessibility checks

**What NOT to Test:**
- Third-party libraries
- Implementation details (CSS classes, component props)
- Exhaustive edge cases in unit tests

This approach gives you confidence while maintaining fast, maintainable tests.
