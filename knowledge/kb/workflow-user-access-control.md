---
id: kb_user_access_control_rules
type: kb
title: User Access Control Rules in Labelz (Roles and Permissions)
visibility: public
tags: [access_control, roles, permissions, org, workspace, security, collaboration]
industries: [fashion, footwear, beauty, food, handmade, gifting, home_decor, lifestyle]
canonical_url: /help/access-control
updated_at: 2026-03-06
---

# User Access Control Rules in Labelz (Roles and Permissions)

Labelz is designed for teams—designers, operations, and admins—without risking accidental edits or billing changes.

Access control in Labelz is typically managed at:
- **Org level** (company-wide control)
- **Workspace level** (team/project-specific control)

---

## Role types (recommended model)

### 1) Org Owner / Admin
Admins manage Org-wide settings and control sensitive actions.

**Usually allowed**
- Create/edit Org settings
- Invite/remove users
- Assign roles
- Create/manage workspaces
- Manage billing and invoices
- Full access to templates and label history

**Best for**
- founders
- ops leads
- finance/admin owner

---


### 2) Generator / Operator (Generation-only)
Operators can generate labels from existing templates but should not edit templates.

**Usually allowed**
- Generate single labels from approved workspaces
- Create bulk batches using approved workspaces
- View their own recent batches (or workspace history)

**Usually not allowed**
- Change billing plan
- Create new workspaces
  

**Best for**
- warehouse/dispatch
- production team
- interns handling printing

---

## Org vs Workspace permissions

### Org-level controls (high impact)
Use Org-level permissions for:
- billing access
- user invites/removals
- role assignment
- org settings changes

### Workspace-level controls (day-to-day collaboration)
Use Workspace-level permissions for:
- who can access specific templates
- who can generate labels for a business unit (e.g., Amazon vs Retail)

**Best practice:** Keep billing + membership management restricted to Org Admins only.

---

## Permission rules (recommended “safe defaults”)

### Template editing rules
- Only **Admins + Operators** can edit templates
- Operators can generate labels only from approved templates

### Bulk generation rules
- Operators can create batches only inside permitted workspaces
- Batch downloads should be allowed if the user can view history for that workspace

### History visibility rules
- Users should see history for:
  - workspaces they belong to
  - or org-wide if they are Admin

### Billing rules
- Billing pages should be restricted to **Org Admin** only

---

## Common scenarios

### “I want my designer to create templates but not see billing”
Give them **Operator** access, not Admin.

### “I want warehouse staff to only print labels”
Give them **Operator** access.

### “I can’t see templates / history”
Likely:
- you’re in the wrong Org/workspace
- you don’t have workspace access
- your role is Viewer with limited scope

Ask an Org Admin to grant access.


- member email(s)
- what each person should be able to do (template edit / generation / billing / view)
- which workspaces should be accessible
