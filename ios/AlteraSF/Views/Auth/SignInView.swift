import SwiftUI

struct SignInView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var email = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var showResetPassword = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    // Header
                    VStack(alignment: .leading, spacing: 8) {
                        Text("AlteraSF")
                            .font(.system(size: 22, weight: .bold))
                            .foregroundColor(AppTheme.primary)
                        Text("Welcome back")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundColor(AppTheme.textPrimary)
                        Text("Sign in to your AlteraSF recruiter dashboard.")
                            .font(.subheadline)
                            .foregroundColor(AppTheme.textSecondary)
                    }
                    .padding(.top, 60)
                    .padding(.bottom, 40)

                    // Form
                    VStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Email")
                                .font(.subheadline).fontWeight(.medium)
                                .foregroundColor(AppTheme.textPrimary)
                            TextField("you@company.com", text: $email)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .textFieldStyle(AlteraTextFieldStyle())
                        }

                        VStack(alignment: .leading, spacing: 6) {
                            Text("Password")
                                .font(.subheadline).fontWeight(.medium)
                                .foregroundColor(AppTheme.textPrimary)
                            HStack {
                                Group {
                                    if showPassword {
                                        TextField("••••••••", text: $password)
                                    } else {
                                        SecureField("••••••••", text: $password)
                                    }
                                }
                                .autocapitalization(.none)
                                Button {
                                    showPassword.toggle()
                                } label: {
                                    Image(systemName: showPassword ? "eye" : "eye.slash")
                                        .foregroundColor(AppTheme.textSecondary)
                                }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(AppTheme.secondaryBackground)
                            .cornerRadius(AppTheme.cornerRadius)
                        }

                        HStack {
                            Spacer()
                            Button("Forgot password?") {
                                showResetPassword = true
                            }
                            .font(.subheadline)
                            .foregroundColor(AppTheme.primary)
                        }

                        if let error = authVM.errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundColor(AppTheme.danger)
                        }

                        Button {
                            authVM.signIn(email: email, password: password)
                        } label: {
                            Group {
                                if authVM.isLoading {
                                    ProgressView()
                                        .progressViewStyle(.circular)
                                        .tint(.white)
                                } else {
                                    Text("Sign In")
                                        .font(.system(size: 16, weight: .semibold))
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 50)
                        }
                        .background(AppTheme.primary)
                        .foregroundColor(.white)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                        .disabled(authVM.isLoading)

                        HStack {
                            Rectangle().frame(height: 1).foregroundColor(AppTheme.divider)
                            Text("or").font(.subheadline).foregroundColor(AppTheme.textSecondary)
                            Rectangle().frame(height: 1).foregroundColor(AppTheme.divider)
                        }

                        Button {
                            authVM.signIn(email: "demo@alterasf.com", password: "demo")
                        } label: {
                            HStack(spacing: 8) {
                                Image(systemName: "globe")
                                Text("Continue with Google")
                                    .font(.system(size: 16, weight: .medium))
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 50)
                        }
                        .background(AppTheme.secondaryBackground)
                        .foregroundColor(AppTheme.textPrimary)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                        .overlay(RoundedRectangle(cornerRadius: AppTheme.buttonCornerRadius)
                            .stroke(AppTheme.divider, lineWidth: 1))
                    }

                    HStack {
                        Text("Don't have an account?")
                            .font(.subheadline)
                            .foregroundColor(AppTheme.textSecondary)
                        Button("Sign up") {}
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(AppTheme.primary)
                    }
                    .padding(.top, 24)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
            .background(AppTheme.background.ignoresSafeArea())
            .navigationDestination(isPresented: $showResetPassword) {
                ResetPasswordView()
            }
        }
    }
}

struct AlteraTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(AppTheme.secondaryBackground)
            .cornerRadius(AppTheme.cornerRadius)
    }
}
