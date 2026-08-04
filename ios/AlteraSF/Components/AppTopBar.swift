import SwiftUI

struct AppTopBar: View {
    @StateObject private var notificationsVM = NotificationsViewModel()
    @State private var showNotifications = false

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
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(AppTheme.background)
        .task { await notificationsVM.load() }
        .sheet(isPresented: $showNotifications) {
            NotificationsPreviewSheet(vm: notificationsVM)
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

