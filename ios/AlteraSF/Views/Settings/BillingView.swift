import SwiftUI

@MainActor
final class BillingViewModel: ObservableObject {
    @Published var billing: APIBillingResponse? = nil
    @Published var isLoading = true
    @Published var error: String? = nil
    @Published var actionError: String? = nil

    private let api = APIService.shared

    func load() async {
        isLoading = true
        error = nil
        do {
            billing = try await api.fetchBilling()
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    /// Returns nil on failure (actionError is set). On success, either the
    /// plan was applied directly, or the account has no live Stripe
    /// subscription to prorate and must complete a real payment first — in
    /// that case the caller should open `paymentRequired`'s URL so the user
    /// can actually pay before the upgrade takes effect.
    func changePlan(tier: String, cycle: String) async -> ChangePlanOutcome? {
        actionError = nil
        do {
            let outcome = try await api.changePlan(tier: tier, cycle: cycle)
            if case .applied = outcome {
                await load()
            }
            return outcome
        } catch {
            actionError = error.localizedDescription
            return nil
        }
    }

    func cancel() async {
        actionError = nil
        do {
            try await api.cancelSubscription()
            await load()
        } catch {
            actionError = error.localizedDescription
        }
    }

    func portalURL() async -> URL? {
        actionError = nil
        do {
            let urlString = try await api.fetchBillingPortalURL()
            return URL(string: urlString)
        } catch {
            actionError = "No payment method on file yet. Contact sales@alterasf.com to set one up."
            return nil
        }
    }
}

struct BillingView: View {
    @StateObject private var vm = BillingViewModel()
    @State private var showUpgradeSheet = false
    @State private var showCancelConfirm = false
    @State private var portalURL: URL? = nil
    @Environment(\.openURL) private var openURL

    var body: some View {
        Group {
            if vm.isLoading && vm.billing == nil {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let err = vm.error, vm.billing == nil {
                ErrorBanner(message: err) { Task { await vm.load() } }
                    .padding(16)
            } else if let billing = vm.billing {
                ScrollView {
                    VStack(spacing: 20) {
                        if let actionError = vm.actionError {
                            Text(actionError)
                                .font(.caption)
                                .foregroundColor(AppTheme.danger)
                                .padding(12)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(AppTheme.danger.opacity(0.1))
                                .cornerRadius(8)
                        }
                        planCard(billing)
                        usageCard(billing)
                        paymentCard(billing)
                        invoicesCard(billing)
                        if !billing.summary.isGrandfathered && billing.summary.status != "canceled" {
                            cancelButton
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 16)
                    .padding(.bottom, 32)
                }
            }
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle("Billing")
        .navigationBarTitleDisplayMode(.large)
        .task { await vm.load() }
        .refreshable { await vm.load() }
        .sheet(isPresented: $showUpgradeSheet) {
            if let billing = vm.billing {
                UpgradeSheet(billing: billing) { tier, cycle in
                    guard let outcome = await vm.changePlan(tier: tier, cycle: cycle) else { return false }
                    switch outcome {
                    case .applied:
                        return true
                    case .paymentRequired(let url):
                        // No live Stripe subscription to upgrade in place —
                        // hand off to a real Stripe checkout to collect payment.
                        openURL(url)
                        return true
                    }
                }
            }
        }
        .confirmationDialog("Cancel your subscription?", isPresented: $showCancelConfirm, titleVisibility: .visible) {
            Button("Cancel Subscription", role: .destructive) { Task { await vm.cancel() } }
            Button("Keep Subscription", role: .cancel) {}
        } message: {
            Text("You'll keep access until the end of your current billing period.")
        }
    }

    // MARK: – Plan card

    private func planCard(_ billing: APIBillingResponse) -> some View {
        let summary = billing.summary
        let plan = billing.plans.first { $0.tier == summary.planTier }
        let price = summary.billingCycle == "yearly" ? (plan?.yearlyPrice ?? 0) : (plan?.monthlyPrice ?? 0)

        return VStack(spacing: 0) {
            LinearGradient(
                colors: [AppTheme.primary, AppTheme.primaryDark],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .frame(height: 6)
            .cornerRadius(AppTheme.cardCornerRadius, corners: [.topLeft, .topRight])

            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Image(systemName: "bolt.fill")
                                .font(.system(size: 12))
                                .foregroundColor(AppTheme.primary)
                            Text(summary.isGrandfathered ? "Grandfathered" : (summary.status == "canceled" ? "Canceled" : "Current Plan"))
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(AppTheme.primary)
                                .textCase(.uppercase)
                        }
                        .padding(.horizontal, 8).padding(.vertical, 4)
                        .background(AppTheme.primaryLight).cornerRadius(6)

                        Text(summary.planDisplay)
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(AppTheme.textPrimary)
                    }
                    Spacer()
                    if !summary.isGrandfathered {
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(price > 0 ? "$\(Int(price))" : "Free")
                                .font(.system(size: 28, weight: .bold))
                                .foregroundColor(AppTheme.textPrimary)
                            Text(summary.billingCycle == "yearly" ? "/ year" : "/ month")
                                .font(.caption).foregroundColor(AppTheme.textSecondary)
                        }
                    }
                }

                Divider()

                HStack(spacing: 20) {
                    if let periodEnd = summary.periodEnd, let date = ISO8601DateFormatter().date(from: periodEnd) {
                        BillingMetric(label: "Next billing", value: date.formatted(.dateTime.month(.abbreviated).day().year()))
                    }
                    BillingMetric(label: "Status", value: summary.status.capitalized, valueColor: summary.status == "active" || summary.isGrandfathered ? AppTheme.success : AppTheme.warning)
                    BillingMetric(label: "Seats", value: "\(summary.seatsUsed)/\(summary.seatsLimit >= 999 ? "∞" : "\(summary.seatsLimit)")")
                }

                if !summary.isGrandfathered {
                    Button {
                        showUpgradeSheet = true
                    } label: {
                        Text("Change Plan")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(AppTheme.primary)
                            .frame(maxWidth: .infinity).frame(height: 40)
                            .background(AppTheme.primaryLight)
                            .cornerRadius(AppTheme.buttonCornerRadius)
                    }
                }
            }
            .padding(16)
            .background(AppTheme.background)
            .cornerRadius(AppTheme.cardCornerRadius, corners: [.bottomLeft, .bottomRight])
        }
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }

    // MARK: – Usage card

    private func usageCard(_ billing: APIBillingResponse) -> some View {
        let summary = billing.summary
        return VStack(alignment: .leading, spacing: 16) {
            Text("Usage this period").font(.system(size: 16, weight: .semibold))

            UsageBar(label: "Active job postings", used: summary.jobsUsed, limit: summary.jobsLimit >= 999 ? 0 : summary.jobsLimit, color: AppTheme.primary)
            UsageBar(label: "Resumes screened this month", used: summary.resumesUsed, limit: summary.resumesLimit >= 999 ? 0 : summary.resumesLimit, color: AppTheme.success)

            HStack(spacing: 12) {
                FeatureAccessBox(label: "Claim Validity", enabled: summary.hasClaimValidity)
                FeatureAccessBox(label: "Red Flag Detection", enabled: summary.hasRedFlag)
                FeatureAccessBox(label: "Full Analytics", enabled: summary.hasAnalytics)
            }
        }
        .padding(16)
        .cardStyle()
    }

    // MARK: – Payment card

    private func paymentCard(_ billing: APIBillingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Payment method").font(.system(size: 16, weight: .semibold))
                Spacer()
                Button(billing.hasStripeCustomer ? "Manage" : "Add") {
                    Task {
                        if let url = await vm.portalURL() { openURL(url) }
                    }
                }
                .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
            }

            if let brand = billing.paymentMethod.brand, let last4 = billing.paymentMethod.last4 {
                HStack(spacing: 14) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color(red: 0.1, green: 0.15, blue: 0.35))
                        .frame(width: 50, height: 32)
                        .overlay(
                            Text(brand.uppercased()).font(.system(size: 11, weight: .bold)).foregroundColor(.white)
                        )
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(brand.capitalized) ending in \(last4)")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(AppTheme.textPrimary)
                        if let m = billing.paymentMethod.expMonth, let y = billing.paymentMethod.expYear {
                            Text("Expires \(m) / \(y)")
                                .font(.caption)
                                .foregroundColor(AppTheme.textSecondary)
                        }
                    }
                    Spacer()
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(AppTheme.success)
                }
                .padding(12)
                .background(AppTheme.secondaryBackground)
                .cornerRadius(10)
            } else {
                Text("No payment method on file.")
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
            }
        }
        .padding(16)
        .cardStyle()
    }

    // MARK: – Invoices

    private func invoicesCard(_ billing: APIBillingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Invoices").font(.system(size: 16, weight: .semibold))
                Spacer()
                if !billing.invoices.isEmpty {
                    ShareLink(item: receiptText(billing.invoices)) {
                        Text("Share all")
                            .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
                    }
                }
            }

            if billing.invoices.isEmpty {
                Text("No invoices yet.")
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
            } else {
                ForEach(billing.invoices) { invoice in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(invoice.description).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                            Text(formattedDate(invoice.createdAt)).font(.caption).foregroundColor(AppTheme.textSecondary)
                        }
                        Spacer()
                        Text(String(format: "$%.2f", invoice.amount)).font(.system(size: 14, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                        ShareLink(item: receiptText([invoice])) {
                            Image(systemName: "square.and.arrow.up").font(.system(size: 16)).foregroundColor(AppTheme.primary).padding(.leading, 8)
                        }
                    }
                    .padding(.vertical, 4)
                    if invoice.id != billing.invoices.last?.id { Divider() }
                }
            }
        }
        .padding(16)
        .cardStyle()
    }

    private var cancelButton: some View {
        Button(role: .destructive) {
            showCancelConfirm = true
        } label: {
            Text("Cancel Subscription")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(AppTheme.danger)
                .frame(maxWidth: .infinity).frame(height: 44)
                .background(AppTheme.danger.opacity(0.1))
                .cornerRadius(AppTheme.buttonCornerRadius)
        }
    }

    private func formattedDate(_ iso: String?) -> String {
        guard let iso, let date = ISO8601DateFormatter().date(from: iso) ?? {
            let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]; return f.date(from: iso)
        }() else { return "" }
        return date.formatted(.dateTime.month(.abbreviated).day().year())
    }

    private func receiptText(_ invoices: [APIInvoice]) -> String {
        invoices.map { "\($0.description) — $\(String(format: "%.2f", $0.amount)) — \(formattedDate($0.createdAt)) — \($0.status)" }
            .joined(separator: "\n")
    }
}

// MARK: – Sub-components

struct BillingMetric: View {
    let label: String; let value: String
    var valueColor: Color = AppTheme.textPrimary
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            Text(value).font(.system(size: 13, weight: .semibold)).foregroundColor(valueColor)
        }
    }
}

struct UsageBar: View {
    let label: String; let used: Int; let limit: Int; let color: Color
    var fraction: Double { limit > 0 ? min(Double(used) / Double(limit), 1.0) : 0 }
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(label).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                Spacer()
                Text(limit > 0 ? "\(used) / \(limit)" : "\(used)")
                    .font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4).fill(AppTheme.secondaryBackground).frame(height: 6)
                    RoundedRectangle(cornerRadius: 4).fill(color).frame(width: geo.size.width * fraction, height: 6)
                }
            }
            .frame(height: 6)
        }
    }
}

struct FeatureAccessBox: View {
    let label: String; let enabled: Bool
    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: enabled ? "checkmark.circle.fill" : "lock.fill")
                .font(.system(size: 18)).foregroundColor(enabled ? AppTheme.success : AppTheme.textTertiary)
            Text(label).font(.system(size: 10)).foregroundColor(AppTheme.textSecondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 12)
        .background(AppTheme.secondaryBackground).cornerRadius(10)
    }
}

struct UpgradeSheet: View {
    @Environment(\.dismiss) var dismiss
    let billing: APIBillingResponse
    let onChoose: (String, String) async -> Bool
    @State private var isSaving = false

    private var upgradeOptions: [APIPlan] {
        let tiers = ["free", "starter", "pro", "ultra"]
        let currentIdx = tiers.firstIndex(of: billing.summary.planTier) ?? 0
        return billing.plans.filter { (tiers.firstIndex(of: $0.tier) ?? 0) > currentIdx }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    ForEach(upgradeOptions) { plan in
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(plan.displayName).font(.title3.weight(.bold))
                                Spacer()
                                Text("$\(Int(plan.monthlyPrice))/mo").font(.system(size: 16, weight: .semibold)).foregroundColor(AppTheme.primary)
                            }
                            ForEach(plan.features) { feature in
                                HStack(spacing: 10) {
                                    Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.success)
                                    Text(feature.name).font(.system(size: 14))
                                }
                            }
                            Button {
                                Task {
                                    isSaving = true
                                    let ok = await onChoose(plan.tier, billing.summary.billingCycle)
                                    isSaving = false
                                    if ok { dismiss() }
                                }
                            } label: {
                                Text("Switch to \(plan.displayName)")
                                    .font(.system(size: 14, weight: .semibold)).foregroundColor(.white)
                                    .frame(maxWidth: .infinity).frame(height: 44)
                                    .background(AppTheme.primary).cornerRadius(AppTheme.buttonCornerRadius)
                            }
                            .disabled(isSaving)
                        }
                        .padding(16).background(AppTheme.secondaryBackground).cornerRadius(12)
                    }

                    if upgradeOptions.isEmpty {
                        VStack(spacing: 8) {
                            Text("You're on our highest plan.")
                                .font(.subheadline).foregroundColor(AppTheme.textSecondary)
                            Link("Contact sales for Enterprise", destination: URL(string: "mailto:sales@alterasf.com")!)
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .padding(.top, 40)
                    }
                }
                .padding(16)
                .padding(.bottom, 32)
            }
            .navigationTitle("Change Plan").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }
}

// Corner radius on specific corners helper
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat; var corners: UIRectCorner
    func path(in rect: CGRect) -> Path {
        Path(UIBezierPath(roundedRect: rect, byRoundingCorners: corners, cornerRadii: CGSize(width: radius, height: radius)).cgPath)
    }
}
