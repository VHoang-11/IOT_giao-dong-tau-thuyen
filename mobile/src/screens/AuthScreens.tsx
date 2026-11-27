import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { ActionBtn, Panel } from '../components/UI';
import { FONT, SHADOWS, TYPOGRAPHY, useTheme } from '../theme';
import { ScreenProps } from '../types/domain';
import { mockForgotPassword, mockRegister } from '../data/mock';

function BrandBanner() {
  const { colors, mode, toggleTheme } = useTheme();
  return (
    <View
      style={[
        styles.brandWell,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.card,
      ]}
    >
      <View style={[styles.brandIconBox, { backgroundColor: colors.cyanContainerBg }]}>
        <Text style={[styles.brandIcon, { color: colors.tech }]}>≋</Text>
      </View>
      <View style={styles.brandTextCol}>
        <Text style={[styles.brandEyebrow, { color: colors.tech }]}>
          IoT • Edge AI • An toàn Hàng hải
        </Text>
        <Text style={[styles.brandTitle, { color: colors.title }]}>
          Smart Vessel Motion Guard
        </Text>
        <Text style={[styles.brandSub, { color: colors.textSecondary }]}>
          Hệ thống giám sát động học chuyển động tàu và phát hiện bất thường TinyML
        </Text>
      </View>
      <Pressable
        onPress={toggleTheme}
        style={[
          styles.themeChip,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
        accessibilityRole="button"
      >
        <Text style={[styles.themeChipText, { color: colors.title }]}>
          {mode === 'light' ? '☀' : '🌙'}
        </Text>
      </Pressable>
    </View>
  );
}

/**
 * Màn hình 1: Đăng nhập Buồng lái
 */
export function LoginScreen({ actions }: ScreenProps) {
  const { colors } = useTheme();
  const [username, setUsername] = useState('operator');
  const [password, setPassword] = useState('demo123');
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');

  const submit = () => {
    if (!actions.login(username, password)) {
      setError('Tên đăng nhập hoặc mật khẩu chưa đúng. Vui lòng kiểm tra lại.');
    } else {
      setError('');
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.root, { backgroundColor: colors.canvas }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <Panel title="Đăng nhập Buồng lái">
          <Text style={[styles.formSubtitle, { color: colors.textSecondary }]}>
            Nhập thông tin định danh sĩ quan trực ca hoặc giám sát viên:
          </Text>

          <Text style={[styles.fieldLabel, { color: colors.title }]}>
            Mã Sĩ quan / Tên đăng nhập
          </Text>
          <TextInput
            value={username}
            onChangeText={(val) => {
              setUsername(val);
              setError('');
            }}
            style={[
              styles.textInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
            autoCapitalize="none"
            autoCorrect={false}
            accessibilityLabel="Tên đăng nhập"
            placeholder="operator / supervisor / admin"
            placeholderTextColor={colors.muted}
          />

          <View style={styles.labelRow}>
            <Text style={[styles.fieldLabel, { color: colors.title }]}>Mật khẩu truy cập</Text>
            <Pressable
              onPress={() => actions.go('ForgotPassword')}
              accessibilityRole="button"
              hitSlop={10}
              style={styles.inlineLinkBtn}
            >
              <Text style={[styles.keyRecoveryText, { color: colors.tech }]}>
                Khôi phục mật mã?
              </Text>
            </Pressable>
          </View>

          <View style={styles.passwordRow}>
            <TextInput
              value={password}
              onChangeText={(val) => {
                setPassword(val);
                setError('');
              }}
              style={[
                styles.textInput,
                {
                  flex: 1,
                  backgroundColor: colors.panel2,
                  borderColor: colors.borderSubtle,
                  color: colors.title,
                },
              ]}
              secureTextEntry={!visible}
              accessibilityLabel="Mật khẩu"
              placeholder="Nhập mật khẩu truy cập"
              placeholderTextColor={colors.muted}
            />
            <Pressable
              onPress={() => setVisible((v) => !v)}
              style={[
                styles.showPassBtn,
                { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
              ]}
              accessibilityRole="button"
            >
              <Text style={[styles.showPassText, { color: colors.tech }]}>
                {visible ? 'Ẩn' : 'Hiện'}
              </Text>
            </Pressable>
          </View>

          {error ? (
            <View
              style={[
                styles.errorBox,
                { backgroundColor: colors.errorContainerBg, borderColor: colors.red },
              ]}
            >
              <Text style={[styles.errorText, { color: colors.red }]}>{error}</Text>
            </View>
          ) : null}

          <View style={{ marginTop: 10 }}>
            <ActionBtn label="Đăng nhập hệ thống →" onPress={submit} tone="primary" />
          </View>

          <View style={[styles.footerNav, { borderTopColor: colors.borderSubtle }]}>
            <Pressable
              onPress={() => actions.go('Register')}
              style={styles.navLink}
              accessibilityRole="button"
            >
              <Text style={[styles.navLinkText, { color: colors.tech }]}>
                Đăng ký tài khoản Sĩ quan trực ca →
              </Text>
            </Pressable>
          </View>
        </Panel>

        <Text style={[styles.complianceNotice, { color: colors.textSecondary }]}>
          Smart Vessel Motion Guard • Phiên bản mô phỏng giao diện di động
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/**
 * Màn hình 2: Đăng ký Sĩ quan
 */
export function RegisterScreen({ actions }: ScreenProps) {
  const { colors } = useTheme();
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [pendingNotice, setPendingNotice] = useState('');

  const submit = () => {
    setError('');
    setPendingNotice('');
    if (!username.trim() || !password) {
      setError('Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp. Vui lòng nhập lại.');
      return;
    }
    if (password.length < 6) {
      setError('Mật khẩu phải có độ dài tối thiểu 6 ký tự.');
      return;
    }

    const res = mockRegister(username, password, fullName);
    if (!res.success) {
      setError(res.error || 'Đăng ký không thành công.');
      return;
    }
    setPendingNotice(res.message);
  };

  return (
    <KeyboardAvoidingView
      style={[styles.root, { backgroundColor: colors.canvas }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <Panel title="Đăng ký Sĩ quan">
          <Text style={[styles.formSubtitle, { color: colors.textSecondary }]}>
            Tạo tài khoản trực ca giám sát động học tàu mới:
          </Text>

          <Text style={[styles.fieldLabel, { color: colors.title }]}>Họ và tên sĩ quan</Text>
          <TextInput
            value={fullName}
            onChangeText={(val) => {
              setFullName(val);
              setError('');
            }}
            style={[
              styles.textInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
            accessibilityLabel="Họ và tên"
            placeholder="Ví dụ: Sĩ quan Nguyễn Văn A"
            placeholderTextColor={colors.muted}
          />

          <Text style={[styles.fieldLabel, { color: colors.title }]}>Tên đăng nhập</Text>
          <TextInput
            value={username}
            onChangeText={(val) => {
              setUsername(val);
              setError('');
            }}
            style={[
              styles.textInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
            autoCapitalize="none"
            autoCorrect={false}
            accessibilityLabel="Tên đăng nhập"
            placeholder="Ví dụ: officer_bridge01"
            placeholderTextColor={colors.muted}
          />

          <Text style={[styles.fieldLabel, { color: colors.title }]}>Mật khẩu truy cập</Text>
          <View style={styles.passwordRow}>
            <TextInput
              value={password}
              onChangeText={(val) => {
                setPassword(val);
                setError('');
              }}
              style={[
                styles.textInput,
                {
                  flex: 1,
                  backgroundColor: colors.panel2,
                  borderColor: colors.borderSubtle,
                  color: colors.title,
                },
              ]}
              secureTextEntry={!visible}
              accessibilityLabel="Mật khẩu"
              placeholder="Tối thiểu 6 ký tự"
              placeholderTextColor={colors.muted}
            />
            <Pressable
              onPress={() => setVisible((v) => !v)}
              style={[
                styles.showPassBtn,
                { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
              ]}
              accessibilityRole="button"
            >
              <Text style={[styles.showPassText, { color: colors.tech }]}>
                {visible ? 'Ẩn' : 'Hiện'}
              </Text>
            </Pressable>
          </View>

          <Text style={[styles.fieldLabel, { color: colors.title }]}>Xác nhận mật khẩu</Text>
          <TextInput
            value={confirmPassword}
            onChangeText={(val) => {
              setConfirmPassword(val);
              setError('');
            }}
            style={[
              styles.textInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
            secureTextEntry={!visible}
            accessibilityLabel="Xác nhận mật khẩu"
            placeholder="Nhập lại mật khẩu"
            placeholderTextColor={colors.muted}
          />

          <View
            style={[
              styles.roleLockBox,
              { backgroundColor: colors.cyanContainerBg, borderColor: colors.borderSubtle },
            ]}
          >
            <Text style={[styles.roleLockTitle, { color: colors.title }]}>
              Phân quyền tài khoản (Bảng 3.1)
            </Text>
            <Text style={[styles.roleLockText, { color: colors.textSecondary }]}>
              Tài khoản tự đăng ký có quyền Sĩ quan trực ca (Operator / Chỉ xem). Quyền Giám sát viên và Quản trị viên do hệ thống cấp phát riêng.
            </Text>
          </View>

          {error ? (
            <View
              style={[
                styles.errorBox,
                { backgroundColor: colors.errorContainerBg, borderColor: colors.red },
              ]}
            >
              <Text style={[styles.errorText, { color: colors.red }]}>{error}</Text>
            </View>
          ) : null}

          {pendingNotice ? (
            <View
              style={[
                styles.pendingNoticeBanner,
                { backgroundColor: colors.warningContainerBg, borderColor: colors.amber },
              ]}
            >
              <Text style={[styles.pendingNoticeTitle, { color: colors.amber }]}>
                Thông báo dịch vụ xác thực
              </Text>
              <Text style={[styles.pendingNoticeText, { color: colors.title }]}>
                {pendingNotice}
              </Text>
              <View style={{ marginTop: 8 }}>
                <ActionBtn
                  label="Chuyển sang Đăng nhập ngay →"
                  onPress={() => actions.go('Login')}
                  tone="primary"
                />
              </View>
            </View>
          ) : (
            <View style={{ marginTop: 10 }}>
              <ActionBtn label="Xác nhận đăng ký →" onPress={submit} tone="primary" />
            </View>
          )}

          <View style={[styles.footerNav, { borderTopColor: colors.borderSubtle }]}>
            <Pressable
              onPress={() => actions.go('Login')}
              style={styles.navLink}
              accessibilityRole="button"
            >
              <Text style={[styles.navLinkText, { color: colors.tech }]}>
                ← Quay lại Đăng nhập
              </Text>
            </Pressable>
          </View>
        </Panel>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/**
 * Màn hình 3: Khôi phục mật mã
 */
export function ForgotPasswordScreen({ actions }: ScreenProps) {
  const { colors } = useTheme();
  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState('');
  const [pendingNotice, setPendingNotice] = useState('');

  const submit = () => {
    setError('');
    setPendingNotice('');
    if (!identifier.trim()) {
      setError('Vui lòng nhập Tên đăng nhập hoặc Email sĩ quan.');
      return;
    }

    const res = mockForgotPassword(identifier);
    if (!res.success) {
      setError(res.error || 'Yêu cầu không hợp lệ.');
      return;
    }
    setPendingNotice(res.message);
  };

  return (
    <KeyboardAvoidingView
      style={[styles.root, { backgroundColor: colors.canvas }]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <Panel title="Khôi phục Mật mã">
          <Text style={[styles.formSubtitle, { color: colors.textSecondary }]}>
            Yêu cầu cấp lại mã truy cập buồng lái hoặc đặt lại mật khẩu:
          </Text>

          <Text style={[styles.fieldLabel, { color: colors.title }]}>
            Mã sĩ quan hoặc Email buồng lái
          </Text>
          <TextInput
            value={identifier}
            onChangeText={(val) => {
              setIdentifier(val);
              setError('');
            }}
            style={[
              styles.textInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
            autoCapitalize="none"
            autoCorrect={false}
            accessibilityLabel="Mã sĩ quan hoặc email"
            placeholder="Ví dụ: operator hoặc officer@vessel01.vn"
            placeholderTextColor={colors.muted}
          />

          {error ? (
            <View
              style={[
                styles.errorBox,
                { backgroundColor: colors.errorContainerBg, borderColor: colors.red },
              ]}
            >
              <Text style={[styles.errorText, { color: colors.red }]}>{error}</Text>
            </View>
          ) : null}

          {pendingNotice ? (
            <View
              style={[
                styles.pendingNoticeBanner,
                { backgroundColor: colors.warningContainerBg, borderColor: colors.amber },
              ]}
            >
              <Text style={[styles.pendingNoticeTitle, { color: colors.amber }]}>
                Trạng thái hạ tầng xác thực
              </Text>
              <Text style={[styles.pendingNoticeText, { color: colors.title }]}>
                {pendingNotice}
              </Text>
              <View style={{ marginTop: 8 }}>
                <ActionBtn
                  label="Quay lại màn hình Đăng nhập"
                  onPress={() => actions.go('Login')}
                  tone="primary"
                />
              </View>
            </View>
          ) : (
            <View style={{ marginTop: 10 }}>
              <ActionBtn label="Gửi yêu cầu đặt lại mật mã →" onPress={submit} tone="primary" />
            </View>
          )}

          <View style={[styles.footerNav, { borderTopColor: colors.borderSubtle }]}>
            <Pressable
              onPress={() => actions.go('Login')}
              style={styles.navLink}
              accessibilityRole="button"
            >
              <Text style={[styles.navLinkText, { color: colors.tech }]}>
                ← Quay lại Đăng nhập
              </Text>
            </Pressable>
          </View>
        </Panel>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 28,
    gap: 14,
  },
  brandWell: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  brandIconBox: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandIcon: {
    fontSize: 24,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  brandTextCol: {
    flex: 1,
    gap: 2,
  },
  brandEyebrow: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  brandTitle: {
    fontSize: 18,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  brandSub: {
    fontSize: 12,
    fontFamily: FONT.regular,
    lineHeight: 16,
  },
  themeChip: {
    width: 40,
    height: 40,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  themeChipText: {
    fontSize: 16,
  },
  formSubtitle: {
    ...TYPOGRAPHY.secondary,
    marginBottom: 4,
  },
  fieldLabel: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    marginTop: 6,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  inlineLinkBtn: {
    minHeight: 36,
    justifyContent: 'center',
  },
  keyRecoveryText: {
    fontSize: 13,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  textInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    fontFamily: FONT.regular,
    minHeight: 46,
    marginTop: 4,
  },
  passwordRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    marginTop: 4,
  },
  showPassBtn: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 14,
    minHeight: 46,
    minWidth: 56,
    alignItems: 'center',
    justifyContent: 'center',
  },
  showPassText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  roleLockBox: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 10,
    gap: 4,
  },
  roleLockTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  roleLockText: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  pendingNoticeBanner: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 10,
    gap: 4,
  },
  pendingNoticeTitle: {
    fontSize: 14,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  pendingNoticeText: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  errorBox: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginTop: 8,
  },
  errorText: {
    fontSize: 13,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  footerNav: {
    borderTopWidth: 1,
    marginTop: 12,
    paddingTop: 12,
    alignItems: 'center',
  },
  navLink: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 8,
  },
  navLinkText: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  complianceNotice: {
    fontSize: 12,
    fontFamily: FONT.regular,
    textAlign: 'center',
  },
});
