# Administrator / owner instruction manual

[All manuals](START-HERE.md) · [Customer response guide](customer-interactions.md)

Your role is to keep customer commitments, schedules, crew agreements, and financial records consistent. Use the crew workspace for normal operations. This guide assumes you have Admin permissions there; the separate **Administration** area requires additional account permissions.

## 1. Daily opening routine

1. Open **Overview**. Review new leads, upcoming jobs, work awaiting approval, and outstanding invoice balances.
2. Open **Notifications** and follow each relevant update to its record.
3. Open **Leads** to assign new requests and check follow-ups.
4. Open **Schedule** and **Jobs & offers** to check today's appointments and missing crew acceptance.
5. Review submitted completions, unpaid invoices, and payable compensation.

An appointment and an accepted crew assignment are separate steps. A booked job still needs an offer and cleaner acceptance before it is fully staffed.

## 2. Set and maintain the price book

1. Open **Price book**.
2. Select **＋ Add service**, or select an existing service name.
3. Enter the name, description, unit, unit price, and category. Choose a unit that matches how you will count the work—for example, window, screen, or visit.
4. Set **Active** to make the item available for new estimates. Use **Requires approval** for items that need office review. Set **Commissionable** according to the business's compensation policy.
5. Select **Save service**.

Use owner-approved amounts. Existing estimates keep their saved prices; changing the price book does not correct a price already quoted to a customer. An inactive service remains in historical records but is unavailable for new estimate selection.

## 3. Receive and assign customer requests

1. Open **Leads**, search for the customer or address, and open the request.
2. Read **The conversation**, existing **Estimates**, and **Activity history** before contacting the customer.
3. Confirm the service address, property type, requested work, access, and preferred timing with the customer.
4. Under **Keep things moving**, set the appropriate status, follow-up time, notes, and **Assigned to** salesperson. Select **Update lead**.
5. If the customer asks not to be contacted, record **Do not contact** and stop routine follow-ups. Do not clear the preference simply to move the lead forward.

For a new office-entered account, use **Customers → New customer**. Open its record to add contacts and service properties. For a doorstep conversation or immediate sales lead, use **Quick lead** instead. Avoid adding a second customer when a matching record already exists.

## 4. Review and send an estimate

1. Open the lead and select **Build estimate**.
2. Select services and quantities. Leave unused rows blank.
3. Enter the approved discount, configured tax rate, expiration date, customer notes, and terms. Tax rates must come from the business's approved configuration.
4. Select **Create estimate** and inspect the service breakdown and total.
5. If it is awaiting pricing review, select **Approve pricing** after checking the exception.
6. Select **Send estimate**. The page displays a secure customer link and queues delivery.
7. Share the link only with the intended customer through the approved communication method. In the local preview, use it for testing on this computer only.

The customer can review the estimate, download a PDF, type their name, check the agreement box, and approve. They can also decline with an optional explanation. Approval saves the terms; it does not schedule an appointment.

**Corrections:** open an unaccepted estimate and choose **Revise estimate**. The form starts with the saved lines and rates. Change quantities, descriptions, units, or prices; use **Add service line** for more rows and check **Delete** to omit a line. Enter a revision reason and select **Save revision**. The original remains in history, its customer links stop working, and the replacement needs its own review, sending, and customer acceptance. An invalid revision leaves the original usable. Accepted estimates cannot be rewritten; coordinate an explicit office change process for already-approved/billed work.

Use **Revoke existing links** when a link was shared incorrectly. For a still-open sent estimate, **Get customer link** can create a fresh link. To reopen a declined or expired proposal, use **Revise estimate**, confirm current scope/expiration, and send the replacement.

## 5. Book and staff approved work

1. Open the accepted estimate and select **Schedule this job**.
2. Enter start and finish in Knoxville time, check the already-reserved windows, and select **Confirm appointment**.
3. Open the job and select **＋ Offer job**.
4. Choose an active cleaner, the agreed fixed pay, offer expiration, and a required crew slot. Use slot 1 for an ordinary one-person job.
5. Select **Send job offer**.
6. Review **Assignments** until the required cleaner has accepted. A sent offer alone is not acceptance.
7. Communicate the confirmed appointment and preparation instructions to the customer through the approved channel.

If a cleaner declines or an offer expires, review the reason/availability and send a replacement offer. If the slot still has an active offer, open it and **Withdraw offer** with a reason before offering that slot again. A cleaner must accept their own offer; do not accept on their behalf using their credentials.

## 6. Handle schedule changes and cancellations

**Change an upcoming appointment:** open the job → **Reschedule appointment** → review the current details → enter the new start, finish, and reason → **Save new appointment**. Conflicts leave the current booking intact. Successful changes supersede active offers and reverse their pending pay agreements. Send fresh offers and get acceptance again. Tell the customer the new confirmed time separately.

**Cancel an appointment:** open the job → **Cancel appointment** → review the consequences → enter the reason → **Cancel appointment**. The job remains in history and active offers are withdrawn. Completed jobs cannot be canceled this way. If work has already started, coordinate with the cleaner and resolve any compensation question before taking action.

**Block unavailable time:** use **Schedule → Block time**, select the staff member or whole-business block, enter the start/end and reason, then save. Use **Edit block** to correct unavailable time, or **Remove block** with a reason to release it. Blocks that conflict with existing booked work or accepted assignments are rejected; reschedule the affected work first. Removal is recorded in audit history.

## 7. Review completion and issue the invoice

1. Open the job awaiting completion review.
2. Review **Job notes & evidence** and the agreed service scope. Confirm checklist completion and resolve open issues with the cleaner.
3. Choose **Approve completion**, or enter a correction reason and choose **Return for correction**.
4. Approval makes the cleaner's fixed pay payable. It does not automatically pay the cleaner or prove that the customer paid.
5. On the completed job, choose **Create invoice**. Enter the due date and purchase order if applicable, then **Issue invoice**.
6. Review the invoice breakdown, balance, and terms. **Open customer view & PDF** produces a customer link; follow it to view/download the document.
7. Use **Queue invoice email** when appropriate. Open **Email deliveries** to check pending messages, attempts, and delivery errors. Choose **Process delivery** or **Retry delivery** when ready. The Delivered view means the configured backend accepted the email; in this preview that backend writes files on this computer.

Invoice amounts come from the accepted estimate. There is no general invoice line-item editor in the current workspace. Resolve scope/price changes before issuing an incorrect invoice.

## 8. Record payments and corrections

1. Verify that the business actually received the payment.
2. Open **Invoices**, select the invoice, and locate **Record a payment**.
3. Enter amount, payment method, reference, and relevant note. Select **Record payment** once.
4. Confirm the new balance and payment-history entry. The site rejects overpayments against the invoice balance.

For an incorrect payment record, use its **Record a reversal** control, enter the reason, and select **Reverse payment**. Then record the correct receipt if necessary. A reversal changes the ledger; it does not send a refund through a bank or payment provider.

To void an invoice, first resolve/reverse any recorded payments as appropriate, then use **Void this invoice** with a reason. Voiding preserves history. Handle financial questions through the office; do not delete ledger records.

## 9. Pay and record staff compensation

Open **Compensation**. The two sections are separate:

| Entry | When it becomes payable/earned | What you do |
| --- | --- | --- |
| Cleaner job pay | Administrator approves completed work | Pay through the approved external process, enter its reference, then **Mark paid**. |
| Sales commission | The associated invoice is fully paid | Verify the saved commission and pay externally, then enter its reference and **Mark paid**. |

**Mark paid** records payment; it does not transfer money. A partial customer payment does not earn the sales commission. Profile or price changes do not rewrite accepted pay agreements. For an incorrect staff payout entry, escalate to the owner/technical maintainer; the workspace does not yet expose every payout-adjustment operation.

## 10. Commercial and recurring work

Use one customer account with separate properties and contacts where appropriate. Confirm who requests work, who grants access, and who receives invoices. Enter purchase-order information when issuing invoices.

From a job, choose **Set up repeat service**, enter plan name, interval in days, duration, next visit, and purchase order, then save. Review the plan under **Schedule**. Use **Edit plan** to change the interval, duration, next visit, or purchase order. Uncheck **Active** to pause future generation; check it and choose a future next visit to resume. Existing jobs are unchanged. **Generate next visit** books the displayed next occurrence immediately and advances the plan only when booking succeeds; the background scheduler can also generate visits when configured. If a conflict appears, resolve it or choose another next visit, then retry. Each generated job still needs cleaner offers. Do not promise that saving a plan confirms all future appointments.

## 11. Team access and configuration

- Open **Staff** to search employees and filter Active, Invited, or Inactive accounts. Select **Invite employee**, enter email/display name, choose one or more roles, then **Create invitation**. The employee sets a password through a three-day invitation. Delivery is local-file-only in this preview.
- Open an employee to edit their display name, phone, skills, internal notes, roles, and **Default commission (%) for future agreements**. Select **Save employee**. Saved historical commission and cleaner-pay agreements do not change. Staff Admin access does not automatically grant unrestricted Administration/superuser access.
- For an expired invitation or returning employee, use **Send new invitation**. This revokes previous invitation links. The account becomes active only after the employee chooses a new password. Use **Revoke invitation** to cancel an unused link. A delivery failure leaves the employee record available so you can issue another invitation after fixing the email configuration.
- To remove an employee, review **Work to hand off**, choose **Deactivate access**, enter a reason, and select **Deactivate employee**. Sign-in, existing sessions, and old invitation links stop working. Open sales leads become unassigned, and upcoming cleaner offers are withdrawn. In-progress work remains intact and the office receives a handoff notification. Review unassigned leads and affected jobs immediately. Historical work, invoices, and earnings are retained.
- You cannot deactivate your own account or a protected owner, or remove your own administrator role. Removing another employee's Salesperson/Cleaner role also releases eligible work for handoff. Protected owner privileges stay in the separate owner configuration.
- Customer account creation/linking currently requires authorized Administration support. Link the correct user to the correct Customer record. A quote submission does not automatically create a portal login. Shared document links can be used without a login.
- For gallery media, use **Administration → Media assets**: enter the original, descriptive text, public visibility, and genuine marketing approval; save, select the asset, and run **Publish approved media and generate responsive files**. Use **Unpublish selected media** to remove publication. Never publish private job evidence without a separate approved marketing asset.
- Use verified content for services, service areas, and testimonials. Testimonials need verification and permission to publish.

## 12. End-of-day review

Check unassigned leads, follow-ups, unanswered/expired offers, unresolved issues, completion reviews, outstanding invoices, and payable compensation. Use **Reports** for business totals and invoice aging; use **Audit history** to investigate changes. Record the next owner/action for unresolved items, and verify customer communications actually happened.
