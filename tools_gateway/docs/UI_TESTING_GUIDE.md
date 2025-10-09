# OAuth Provider UI - Testing Guide

**Date:** October 8, 2025
**Component:** OAuth Provider Management Interface
**Location:** `test_mcp.html` → OAuth Providers Tab

## Overview

This guide provides step-by-step instructions for testing the OAuth Provider Management UI that was added to the Tools Gateway portal. The UI allows administrators to configure OAuth 2.1 providers without editing configuration files.

## Prerequisites

Before testing, ensure:
- ✅ Gateway server is running on `http://localhost:8021`
- ✅ All enterprise security modules are installed
- ✅ Browser supports modern JavaScript (ES6+)
- ✅ You have admin credentials or OAuth provider access

## Test Environment Setup

### 1. Start the Gateway Server

```bash
cd /Users/deepankar/Documents/mcp_gateway/tools_gateway
python main.py
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8021
```

### 2. Open the Portal

```bash
open http://localhost:8021
```

Or navigate to `http://localhost:8021` in your browser.

### 3. Verify Files Loaded

Open browser DevTools (F12) and check Console for errors. You should see:
- No JavaScript errors
- `admin-security.js` loaded successfully
- `oauth-forms.css` stylesheet applied

**Check in Network Tab:**
- ✅ `GET /static/js/admin-security.js` → 200 OK
- ✅ `GET /static/css/oauth-forms.css` → 200 OK

---

## UI Component Testing

### Test 1: OAuth Providers Tab Navigation ✅

**Objective:** Verify the OAuth Providers tab is visible and clickable

**Steps:**
1. Look at the left sidebar navigation
2. Find the "OAuth Providers" tab (should have a key icon 🔑)
3. Click on "OAuth Providers"

**Expected Results:**
- ✅ Tab highlights when selected
- ✅ Main content area switches to OAuth Providers view
- ✅ "Add OAuth Provider" button is visible
- ✅ "Setup Guide" button is visible
- ✅ "Refresh" button is visible

**Screenshot Checkpoints:**
- Toolbar with 3 buttons (Add, Setup Guide, Refresh)
- Empty providers list or existing provider cards

---

### Test 2: Add OAuth Provider Modal ✅

**Objective:** Verify the Add OAuth Provider modal opens and displays correctly

**Steps:**
1. Click the **"Add OAuth Provider"** button
2. Wait for modal to appear

**Expected Results:**
- ✅ Modal overlay darkens the background
- ✅ Modal has title: "Add OAuth Provider"
- ✅ Form contains all required fields:
  - Provider Template dropdown
  - Provider ID input
  - Provider Name input
  - Client ID input
  - Client Secret input (password type)
  - Authorization URL input
  - Token URL input
  - User Info URL input
  - Scopes section with tags container
  - Advanced Options section (collapsed)
- ✅ "Cancel" and "Save Provider" buttons visible

**Screenshot Checkpoints:**
- Modal is centered on screen
- All form sections have icons (📋, 🔑, 🌐)
- Form has proper spacing and styling

---

### Test 3: Provider Template Selection ✅

**Objective:** Verify template auto-fill functionality

**Steps:**
1. Open the Add OAuth Provider modal
2. Click the **Provider Template** dropdown
3. Select **"Google OAuth"**

**Expected Results:**
- ✅ Provider ID auto-fills to: `google`
- ✅ Provider Name auto-fills to: `Google`
- ✅ Authorization URL auto-fills to: `https://accounts.google.com/o/oauth2/v2/auth`
- ✅ Token URL auto-fills to: `https://oauth2.googleapis.com/token`
- ✅ User Info URL auto-fills to: `https://www.googleapis.com/oauth2/v2/userinfo`
- ✅ Scopes auto-populate: `openid`, `email`, `profile` (as tags)

**Repeat for:**
- **Microsoft OAuth** → Verify Microsoft endpoints
- **GitHub OAuth** → Verify GitHub endpoints
- **Custom Provider** → Verify all fields clear

**Screenshot Checkpoints:**
- Tags appear in scopes container with blue background
- All URLs are properly formatted

---

### Test 4: Scope Management ✅

**Objective:** Verify scope adding and removing functionality

**Steps:**
1. In the Add OAuth Provider modal
2. Find the "Scopes" section
3. Type `test:scope` in the scope input field
4. Click **"Add"** button

**Expected Results:**
- ✅ New tag appears with text "test:scope"
- ✅ Tag has blue background (`#3498db`)
- ✅ Tag has an "×" button
- ✅ Input field clears after adding

**Steps to Remove:**
1. Click the **"×"** button on the `test:scope` tag

**Expected Results:**
- ✅ Tag is removed from the container
- ✅ Tag disappears smoothly

**Edge Cases to Test:**
- Add empty scope → Should not create tag
- Add duplicate scope → Should not create duplicate
- Remove last scope → Container should remain visible

---

### Test 5: Form Validation ✅

**Objective:** Verify client-side form validation

**Test 5a: Empty Required Fields**

**Steps:**
1. Open Add OAuth Provider modal
2. Leave all fields empty
3. Click **"Save Provider"**

**Expected Results:**
- ✅ Alert appears: "Please fill in all required fields"
- ✅ Modal remains open
- ✅ Provider is NOT saved

**Test 5b: Invalid Provider ID**

**Steps:**
1. Open Add OAuth Provider modal
2. Enter Provider ID: `Google OAuth` (with spaces and uppercase)
3. Fill in other required fields
4. Click **"Save Provider"**

**Expected Results:**
- ✅ Alert appears: "Provider ID must be lowercase, no spaces"
- ✅ Provider is NOT saved

**Valid Provider ID formats to test:**
- ✅ `google` (lowercase, alphabetic)
- ✅ `google_oauth` (underscore allowed)
- ✅ `google-oauth` (hyphen allowed)
- ✅ `google123` (numbers allowed)

**Test 5c: Missing Scopes**

**Steps:**
1. Open Add OAuth Provider modal
2. Fill in all required fields
3. Remove all scopes (if any)
4. Click **"Save Provider"**

**Expected Results:**
- ✅ Alert appears: "Please add at least one scope"
- ✅ Provider is NOT saved

---

### Test 6: Save OAuth Provider ✅

**Objective:** Verify provider configuration is saved successfully

**Steps:**
1. Open Add OAuth Provider modal
2. Select **"Google OAuth"** template
3. Enter Client ID: `test-client-id-123456`
4. Enter Client Secret: `test-secret-abcdef`
5. Verify scopes are present
6. Click **"Save Provider"**

**Expected Results:**
- ✅ Success message appears: "OAuth provider added successfully"
- ✅ Modal closes automatically
- ✅ New provider card appears in the providers list

**Provider Card Should Display:**
- ✅ Google icon (🔑 or provider-specific icon)
- ✅ Provider Name: "Google"
- ✅ Provider ID: `google`
- ✅ Scopes listed: `openid`, `email`, `profile`
- ✅ Status badge: "Enabled" (green background)
- ✅ "Remove" button

**Screenshot Checkpoints:**
- Provider card has hover effect
- Status badge is properly styled

---

### Test 7: OAuth Setup Guide Modal ✅

**Objective:** Verify setup guide displays provider-specific instructions

**Steps:**
1. Click the **"Setup Guide"** button in the toolbar
2. Wait for modal to appear

**Expected Results:**
- ✅ Modal opens with title "OAuth Provider Setup Guide"
- ✅ Three sections visible:
  1. **Google OAuth Setup**
  2. **Microsoft OAuth Setup**
  3. **GitHub OAuth Setup**
- ✅ Each section contains:
  - Provider icon
  - Numbered steps (ol/li)
  - Links to developer consoles
  - Code blocks with redirect URIs
  - Clear instructions

**Content Verification:**
- ✅ Google section links to `https://console.cloud.google.com/`
- ✅ Microsoft section links to `https://portal.azure.com/`
- ✅ GitHub section links to `https://github.com/settings/developers`
- ✅ All redirect URIs show: `http://localhost:8021/auth/callback`

**Screenshot Checkpoints:**
- Setup guide has proper formatting
- Code blocks are styled with grey background
- Links are blue and underlined on hover

---

### Test 8: Refresh Providers List ✅

**Objective:** Verify providers list can be refreshed from server

**Steps:**
1. Ensure at least one provider is configured
2. Click the **"Refresh"** button in the toolbar

**Expected Results:**
- ✅ Brief loading state (optional)
- ✅ Providers list reloads
- ✅ All configured providers appear
- ✅ Provider cards display correct information

**API Call Verification (DevTools Network Tab):**
- ✅ `GET /auth/providers` → 200 OK
- ✅ Response JSON contains provider list

---

### Test 9: Remove OAuth Provider ✅

**Objective:** Verify provider can be removed

**Steps:**
1. Find a provider card in the list
2. Click the **"Remove"** button
3. Confirm deletion (if prompt appears)

**Expected Results:**
- ✅ Provider card is removed from the list
- ✅ Success message appears: "Provider removed successfully"
- ✅ API call succeeds

**API Call Verification (DevTools Network Tab):**
- ✅ `DELETE /admin/oauth/providers/{provider_id}` → 200 OK

**Edge Cases:**
- Remove the last provider → Empty state should display
- Remove while user is logged in with that provider → User remains logged in (session persists)

---

### Test 10: Advanced Options Toggle ✅

**Objective:** Verify advanced options can be expanded/collapsed

**Steps:**
1. Open Add OAuth Provider modal
2. Find the "Advanced Options" section
3. Click on the section header

**Expected Results:**
- ✅ Section expands to show hidden fields
- ✅ "Enable this provider" checkbox is visible
- ✅ Checkbox is checked by default
- ✅ Clicking again collapses the section

**Functionality Test:**
1. Uncheck "Enable this provider"
2. Save the provider
3. Verify provider card shows "Disabled" badge (red background)

---

### Test 11: Modal Keyboard Interactions ✅

**Objective:** Verify keyboard navigation and shortcuts

**Test 11a: Escape Key Closes Modal**

**Steps:**
1. Open Add OAuth Provider modal
2. Press **ESC** key

**Expected Results:**
- ✅ Modal closes
- ✅ Background overlay disappears

**Test 11b: Enter Key Adds Scope**

**Steps:**
1. Open Add OAuth Provider modal
2. Click in the scope input field
3. Type `custom:scope`
4. Press **Enter** key

**Expected Results:**
- ✅ Scope is added as a tag
- ✅ Input field clears

**Test 11c: Tab Navigation**

**Steps:**
1. Open Add OAuth Provider modal
2. Press **Tab** repeatedly

**Expected Results:**
- ✅ Focus moves through all form fields in order
- ✅ Focus is visible (outline or highlight)
- ✅ Can reach all interactive elements

---

### Test 12: Responsive Design ✅

**Objective:** Verify UI works on different screen sizes

**Test 12a: Desktop (1920x1080)**

**Steps:**
1. Open portal in full-screen browser
2. Navigate to OAuth Providers tab

**Expected Results:**
- ✅ Provider cards display in grid (multiple columns)
- ✅ Modal is centered with max-width 800px
- ✅ All elements are properly spaced

**Test 12b: Tablet (768px width)**

**Steps:**
1. Resize browser window to 768px width
2. Navigate to OAuth Providers tab

**Expected Results:**
- ✅ Provider cards switch to single column
- ✅ Form rows stack vertically
- ✅ Modal adjusts to screen width

**Test 12c: Mobile (375px width)**

**Steps:**
1. Resize browser window to 375px width
2. Open Add OAuth Provider modal

**Expected Results:**
- ✅ Modal takes up 95% of screen width
- ✅ All form fields are readable
- ✅ Buttons stack if necessary

---

### Test 13: CSS Styling Verification ✅

**Objective:** Verify all CSS styles are applied correctly

**Elements to Check:**

1. **Modal Large** (`.modal-large`)
   - ✅ Max-width: 800px
   - ✅ Max-height: 90vh
   - ✅ Overflow-y: auto

2. **Form Section Title** (`.form-section-title`)
   - ✅ Font-weight: 600
   - ✅ Color: #2c3e50
   - ✅ Icon color: #3498db

3. **Tags Container** (`.tags-container`)
   - ✅ Background: #f8f9fa
   - ✅ Border: 1px solid #ddd
   - ✅ Min-height: 50px

4. **Tag** (`.tag`)
   - ✅ Background: #3498db
   - ✅ Color: white
   - ✅ Border-radius: 20px

5. **Provider Card** (`.provider-card`)
   - ✅ Border: 1px solid #e0e0e0
   - ✅ Border-radius: 12px
   - ✅ Hover effect: border-color changes to #3498db
   - ✅ Hover effect: box-shadow appears

6. **Badge** (`.badge-success`, `.badge-danger`)
   - ✅ Enabled badge: green background (#d4edda)
   - ✅ Disabled badge: red background (#f8d7da)

---

## Integration Testing

### Test 14: End-to-End OAuth Flow ✅

**Objective:** Test complete OAuth provider configuration and authentication flow

**Prerequisites:**
- Real OAuth credentials from Google/Microsoft/GitHub
- Follow setup instructions in `OAUTH_UI_GUIDE.md`

**Steps:**

1. **Configure Provider via UI**
   - Open portal → OAuth Providers tab
   - Click "Add OAuth Provider"
   - Select "Google OAuth" template
   - Enter real Client ID and Client Secret
   - Save provider

2. **Verify Provider Appears**
   - Check providers list
   - Verify "Enabled" badge

3. **Test Login Flow**
   - Open new incognito window
   - Navigate to `http://localhost:8021`
   - Click "Sign in with Google"
   - Complete OAuth authorization
   - Verify redirect back to portal

4. **Verify Authentication**
   - Check user email appears in header
   - Verify JWT token in localStorage
   - Check audit logs for login event

**Expected Results:**
- ✅ OAuth provider configured successfully
- ✅ Login redirects to Google
- ✅ User authenticates and returns to portal
- ✅ User session is active
- ✅ Audit log records `auth.login.success`

---

### Test 15: API Endpoint Testing ✅

**Objective:** Verify OAuth management API endpoints

**Test 15a: List Providers**

```bash
curl http://localhost:8021/auth/providers
```

**Expected Response:**
```json
{
  "providers": [
    {
      "provider_id": "google",
      "provider_name": "Google",
      "enabled": true,
      "scopes": ["openid", "email", "profile"]
    }
  ]
}
```

**Test 15b: Add Provider (Requires Admin JWT)**

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "github",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "provider_name": "GitHub",
    "authorize_url": "https://github.com/login/oauth/authorize",
    "token_url": "https://github.com/login/oauth/access_token",
    "userinfo_url": "https://api.github.com/user",
    "scopes": ["read:user", "user:email"],
    "enabled": true
  }' \
  http://localhost:8021/admin/oauth/providers
```

**Expected Response:**
```json
{
  "message": "OAuth provider added successfully",
  "provider_id": "github"
}
```

**Test 15c: Delete Provider (Requires Admin JWT)**

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8021/admin/oauth/providers/github
```

**Expected Response:**
```json
{
  "message": "OAuth provider removed successfully"
}
```

---

## Browser Compatibility Testing

### Test 16: Cross-Browser Verification ✅

**Browsers to Test:**
- ✅ Google Chrome (latest)
- ✅ Mozilla Firefox (latest)
- ✅ Safari (latest)
- ✅ Microsoft Edge (latest)

**Features to Verify in Each Browser:**
1. Modal opens/closes correctly
2. Form inputs accept text
3. Scopes can be added/removed
4. Provider cards display correctly
5. API calls succeed
6. CSS animations work

---

## Error Handling Testing

### Test 17: Network Error Handling ✅

**Objective:** Verify graceful handling of network errors

**Test 17a: Offline Mode**

**Steps:**
1. Open DevTools → Network tab
2. Check "Offline" mode
3. Try to save a provider

**Expected Results:**
- ✅ Error message appears: "Network error. Please check your connection."
- ✅ Provider is NOT saved
- ✅ Modal remains open

**Test 17b: Server Error (500)**

**Steps:**
1. Mock server error (if possible)
2. Try to save a provider

**Expected Results:**
- ✅ Error message appears with server error details
- ✅ User is informed to try again

---

### Test 18: Authorization Error Handling ✅

**Objective:** Verify permission-based access control

**Test 18a: Non-Admin User**

**Steps:**
1. Login as a non-admin user (no `oauth:manage` permission)
2. Navigate to OAuth Providers tab
3. Try to add a provider

**Expected Results:**
- ✅ "Add OAuth Provider" button is disabled OR
- ✅ API returns 403 Forbidden
- ✅ Error message: "Insufficient permissions"

---

## Performance Testing

### Test 19: Large Provider List ✅

**Objective:** Verify UI handles many providers efficiently

**Steps:**
1. Add 10+ OAuth providers
2. Navigate to OAuth Providers tab
3. Observe rendering performance

**Expected Results:**
- ✅ Page loads in < 2 seconds
- ✅ All provider cards render correctly
- ✅ Scrolling is smooth
- ✅ No JavaScript errors

---

### Test 20: Form Interaction Performance ✅

**Objective:** Verify form interactions are responsive

**Steps:**
1. Open Add OAuth Provider modal
2. Type rapidly in input fields
3. Add/remove scopes quickly
4. Switch templates multiple times

**Expected Results:**
- ✅ Input lag < 50ms
- ✅ Template switching is instant
- ✅ Scope tags update immediately
- ✅ No memory leaks (check DevTools Memory tab)

---

## Accessibility Testing

### Test 21: Screen Reader Compatibility ✅

**Objective:** Verify UI is accessible to screen readers

**Tools:** VoiceOver (Mac), NVDA (Windows), or JAWS

**Steps:**
1. Enable screen reader
2. Navigate to OAuth Providers tab
3. Tab through all interactive elements

**Expected Results:**
- ✅ All buttons have descriptive labels
- ✅ Form fields have associated labels
- ✅ Modal has proper ARIA attributes
- ✅ Focus order is logical

---

### Test 22: Keyboard-Only Navigation ✅

**Objective:** Verify UI can be used without a mouse

**Steps:**
1. Disconnect mouse or use Tab/Shift+Tab only
2. Navigate entire OAuth Providers interface
3. Add, edit, and remove providers using only keyboard

**Expected Results:**
- ✅ All interactive elements are reachable
- ✅ Focus indicators are visible
- ✅ Enter key activates buttons
- ✅ Escape key closes modals

---

## Security Testing

### Test 23: Client Secret Encryption ✅

**Objective:** Verify client secrets are encrypted before storage

**Steps:**
1. Add a provider with Client Secret: `super-secret-123`
2. Check storage file: `oauth_providers.json` or database

**Expected Results:**
- ✅ Client secret is NOT stored in plaintext
- ✅ Encrypted value looks like: `gAAAAA...` (Fernet format)
- ✅ Original secret is not visible in any API response

---

### Test 24: XSS Prevention ✅

**Objective:** Verify UI prevents cross-site scripting attacks

**Steps:**
1. Try to add a provider with malicious script in name:
   - Provider Name: `<script>alert('XSS')</script>`
2. Save provider

**Expected Results:**
- ✅ Script does NOT execute
- ✅ Name is sanitized or escaped
- ✅ Provider card displays literal text, not executed code

---

## Documentation Verification

### Test 25: Setup Guide Accuracy ✅

**Objective:** Verify setup guide instructions are accurate

**Steps:**
1. Follow `OAUTH_UI_GUIDE.md` step-by-step
2. Configure a real OAuth provider (Google, Microsoft, or GitHub)
3. Complete full authentication flow

**Expected Results:**
- ✅ All steps in guide are accurate
- ✅ Screenshots/examples match actual UI
- ✅ OAuth flow completes successfully

---

## Test Results Summary

After completing all tests, fill out this checklist:

### ✅ Core Functionality
- [ ] OAuth Providers tab displays correctly
- [ ] Add OAuth Provider modal opens/closes
- [ ] Template selection auto-fills fields
- [ ] Scopes can be added/removed
- [ ] Form validation works
- [ ] Provider can be saved successfully
- [ ] Provider cards display correctly
- [ ] Providers can be removed

### ✅ User Experience
- [ ] Setup guide is helpful and accurate
- [ ] Error messages are clear
- [ ] Loading states are visible
- [ ] Animations are smooth
- [ ] Refresh button updates list

### ✅ Security
- [ ] Client secrets are encrypted
- [ ] XSS attacks prevented
- [ ] Permission checks enforced
- [ ] CSRF protection active

### ✅ Compatibility
- [ ] Works in Chrome
- [ ] Works in Firefox
- [ ] Works in Safari
- [ ] Works in Edge
- [ ] Responsive on mobile

### ✅ Accessibility
- [ ] Keyboard navigation works
- [ ] Screen reader compatible
- [ ] Focus indicators visible
- [ ] ARIA labels present

---

## Known Issues

Document any bugs or issues found during testing:

| Issue # | Description | Severity | Status |
|---------|-------------|----------|--------|
| 1       | (Example: Modal scrolling on mobile) | Low | Open |

---

## Next Steps

After completing UI testing:

1. **Document Test Results** → Update this file with pass/fail status
2. **File Bug Reports** → Create issues for any failures
3. **Test End-to-End OAuth Flow** → Verify authentication with real providers
4. **Performance Optimization** → Address any performance issues
5. **Production Deployment** → Follow `ENTERPRISE_SECURITY_GUIDE.md`

---

## Support

For testing questions or issues:
- Review `OAUTH_UI_GUIDE.md` for user instructions
- Check `TEST_RESULTS.md` for automated test results
- Consult `ENTERPRISE_SECURITY_GUIDE.md` for deployment guidance

---

**Test Status:** Ready for Testing 🚀
**Last Updated:** October 8, 2025
**Tested By:** ___________
**Overall Result:** ⬜ PASS / ⬜ FAIL
