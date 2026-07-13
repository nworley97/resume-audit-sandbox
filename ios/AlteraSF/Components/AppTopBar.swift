import SwiftUI

struct AppTopBar: View {
    @EnvironmentObject var authVM: AuthViewModel
    @StateObject private var notificationsVM = NotificationsViewModel()
    @State private var showNotifications = false
    @State private var showActivity = false
    @State private var showAccount = false

    var body: some View {
        HStack(spacing: 14) {
            HStack(spacing: 8) {
                Circle()
                    .fill(LinearGradient(colors: [Color(red: 0.12, green: 0.42, blue: 0.85), AppTheme.primary],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 26, height: 26)
                Text("AlteraSF")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)
            }

            Spacer()

            Button { showNotifications = true } label: {
                ZStack(alignment: .topTrailing) {
                    Image(systemName: "bell").font(.system(size: 17)).foregroundColor(AppTheme.textPrimary)
                    if notificationsVM.unreadCount > 0 {
                        Circle().fill(AppTheme.danger).frame(width: 7, height: 7).offset(x: 3, y: -2)
                    }
                }
            }

            Button { showActivity = true } label: {
                Image(systemName: "clock.arrow.circlepath").font(.system(size: 17)).foregroundColor(AppTheme.textPrimary)
            }

            Button { showAccount = true } label: {
                AvatarView(initials: authVM.currentUserInitials, size: 30)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(AppTheme.background)
        .task { await notificationsVM.load() }
        .sheet(isPresented: $showNotifications) {
            NotificationsPreviewSheet(vm: notificationsVM)
        }
        .sheet(isPresented: $showActivity) {
            RecentActivitySheet(vm: notificationsVM)
        }
        .sheet(isPresented: $showAccount) {
            AccountSheet()
        }
    }
}

struct PageHeader: View {
    let title: String
    let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.system(size: 28, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text(subtitle).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 12)
    }
}

struct NotificationsPreviewSheet: View {
    @ObservedObject var vm: NotificationsViewModel
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if vm.notifications.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "bell.slash").font(.system(size: 32)).foregroundColor(AppTheme.textTertiary)
                        Text("No notifications yet").foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 48)
                } else {
                    ForEach(vm.notifications.prefix(5)) { notif in
                        NotificationRow(notification: notif)
                            .onTapGesture { Task { await vm.markRead(notif) } }
                    }
                    NavigationLink {
                        NotificationsView()
                    } label: {
                        Text("View all notifications")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(AppTheme.primary)
                            .frame(maxWidth: .infinity).padding(.vertical, 16)
                    }
                }
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Mark all read") { Task { await vm.markAllRead() } }
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(AppTheme.primary)
                        .disabled(vm.unreadCount == 0)
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

struct RecentActivitySheet: View {
    @ObservedObject var vm: NotificationsViewModel
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if vm.notifications.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "clock").font(.system(size: 32)).foregroundColor(AppTheme.textTertiary)
                        Text("No recent activity").foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 48)
                } else {
                    ForEach(vm.notifications.prefix(5)) { notif in
                        NotificationRow(notification: notif)
                    }
                }
            }
            .navigationTitle("Recent activity")
            .navigationBarTitleDisplayMode(.inline)
        }
        .presentationDetents([.medium, .large])
    }
}

struct AccountSheet: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) var dismiss
    @AppStorage("appearance_mode") private var appearanceModeRaw = AppearanceMode.system.rawValue
    @State private var showSettings = false
    @State private var showHelp = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 14) {
                AvatarView(initials: authVM.currentUserInitials, size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(authVM.currentUserName).font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                    Text(authVM.currentUserEmail).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                }
                Spacer()
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 14)

            Divider()

            row(icon: "gearshape", label: "Account settings") { showSettings = true }
            row(icon: "moon", label: isDark ? "Switch to light mode" : "Switch to dark mode") {
                appearanceModeRaw = isDark ? AppearanceMode.light.rawValue : AppearanceMode.dark.rawValue
            }
            row(icon: "questionmark.circle", label: "Help & support") { showHelp = true }

            Divider().padding(.top, 4)

            Button {
                dismiss()
                authVM.signOut()
            } label: {
                HStack(spacing: 14) {
                    Image(systemName: "rectangle.portrait.and.arrow.right").font(.system(size: 16)).foregroundColor(AppTheme.danger).frame(width: 20)
                    Text("Log out").font(.system(size: 16)).foregroundColor(AppTheme.danger)
                    Spacer()
                }
                .padding(.horizontal, 20).padding(.vertical, 13)
            }
        }
        .padding(.bottom, 16)
        .presentationDetents([.height(320)])
        .sheet(isPresented: $showSettings) { NavigationStack { SettingsView() } }
        .sheet(isPresented: $showHelp) { NavigationStack { HelpSupportView() } }
    }

    private var isDark: Bool { AppearanceMode(rawValue: appearanceModeRaw) == .dark }

    private func row(icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon).font(.system(size: 16)).foregroundColor(AppTheme.textPrimary).frame(width: 20)
                Text(label).font(.system(size: 16)).foregroundColor(AppTheme.textPrimary)
                Spacer()
            }
            .padding(.horizontal, 20).padding(.vertical, 13)
        }
    }
}
