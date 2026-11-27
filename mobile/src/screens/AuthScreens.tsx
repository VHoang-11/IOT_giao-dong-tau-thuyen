import React, { useState } from 'react';
import { ActivityIndicator } from 'react-native';
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
import { C, SHADOWS } from '../theme';
import { DataMode, ScreenProps } from '../types/domain';
import { mockRegister, mockForgotPassword } from '../data/mock';

/**
 * Brand banner common to all Authentication views.
 */
function BrandBanner() {
  return (
    <View style={styles.brandWell}>
      <View style={styles.brandIconBox}>
        <Text style={styles.brandIcon}>≋</Text>
      </View>
      <View style={styles.brandTextCol}>
        <Text style={styles.brandEyebrow}>IOT • EDGE AI • MARITIME SAFETY</Text>
        <Text style={styles.brandTitle}>Smart Vessel Motion Guard</Text>
        <Text style={styles.brandSub}>
          Hệ thống giám sát động học chuyển động tàu (TV4 Mock)
        </Text>
      </View>
    </View>
  );
}

/**
 * Stitch corner reticle accents.
 */
function ReticleAccents() {
  return (
    <>
      <View style={styles.reticleTL} pointerEvents="none" />
      <View style={styles.reticleTR} pointerEvents="none" />
      <View style={styles.reticleBL} pointerEvents="none" />
      <View style={styles.reticleBR} pointerEvents="none" />
    </>
  );
}

/**
 * Hardware security RSA-4096 notice box.
 */
function SecurityNotice() {
  return (
    <View style={styles.secNoticeBox}>
      <Text style={styles.secNoticeIcon}>🔒</Text>
      <Text style={styles.secNoticeText}>
        RSA-4096 BRIDGE HARDWARE KEY ENCRYPTED • M4 DEMO
      </Text>
    </View>
  );
}

/**
 * VIEW 1: Bridge Login Screen
 */
export function LoginScreen({ actions }: ScreenProps) {
  const [mode, setMode] = useState<DataMode>('live');
  const [url, setUrl] = useState(
    process.env.EXPO_PUBLIC_API_URL ?? (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000')
  );
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const switchMode = (next: DataMode) => {
    setMode(next);
    setError('');
    // MOCK dùng tài khoản demo; LIVE dùng tài khoản thật trên Backend (không điền sẵn mật khẩu).
    setUsername(next === 'mock' ? 'operator' : '');
    setPassword(next === 'mock' ? 'demo123' : '');
  };

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const r = await actions.login(username, password, { mode, url });
      if (!r.ok) setError(r.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <View style={styles.cardWrapper}>
          <ReticleAccents />

          <Panel title="ACCESS CONTROL LEVEL 1" tag="SYS_ID: 994-IMU-BRG">
            <Text style={styles.formTitle}>Đăng nhập Buồng lái</Text>
            <Text style={styles.formSubtitle}>
              Nhập mã sĩ quan trực ca hoặc cán bộ giám sát buồng lái:
            </Text>

            <Text style={styles.fieldLabel}>NGUỒN DỮ LIỆU</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12 }}>
              {(['live', 'mock'] as const).map((m) => (
                <Pressable
                  key={m}
                  onPress={() => switchMode(m)}
                  accessibilityRole="button"
                  style={{
                    flex: 1,
                    paddingVertical: 9,
                    borderRadius: 6,
                    alignItems: 'center',
                    borderWidth: 1.5,
                    borderColor: mode === m ? C.cyan : C.border,
                    backgroundColor: mode === m ? '#EAF2FA' : C.panel,
                  }}
                >
                  <Text style={{ color: mode === m ? C.cyan : C.muted, fontSize: 11, fontWeight: '800', fontFamily: 'monospace' }}>
                    {m === 'live' ? 'LIVE (BACKEND THẬT)' : 'MOCK (DEMO)'}
                  </Text>
                </Pressable>
              ))}
            </View>

            {mode === 'live' && (
              <>
                <Text style={styles.fieldLabel}>ĐỊA CHỈ BACKEND</Text>
                <TextInput
                  value={url}
                  onChangeText={(val) => {
                    setUrl(val);
                    setError('');
                  }}
                  style={styles.textInput}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  accessibilityLabel="Địa chỉ Backend"
                  placeholder="http://192.168.1.10:8000"
                  placeholderTextColor={C.muted}
                />
                <Text style={[styles.formSubtitle, { marginTop: 4 }]}>
                  Emulator Android dùng 10.0.2.2; điện thoại thật dùng IP LAN của máy chạy Backend (cùng Wi‑Fi).
                </Text>
              </>
            )}

            <Text style={styles.fieldLabel}>TÊN ĐĂNG NHẬP / OFFICER ID</Text>
            <TextInput
              value={username}
              onChangeText={(val) => {
                setUsername(val);
                setError('');
              }}
              style={styles.textInput}
              autoCapitalize="none"
              accessibilityLabel="Tên đăng nhập"
              placeholder={mode === 'mock' ? 'operator / supervisor / admin' : 'Tài khoản Backend'}
              placeholderTextColor={C.muted}
            />

            <View style={styles.labelRow}>
              <Text style={styles.fieldLabel}>MẬT MÃ BUỒNG LÁI / PASSCODE</Text>
              {mode === 'mock' && (
                <Pressable
                  onPress={() => actions.go('ForgotPassword')}
                  accessibilityRole="button"
                  hitSlop={8}
                >
                  <Text style={styles.keyRecoveryText}>KEY_RECOVERY</Text>
                </Pressable>
              )}
            </View>

            <View style={styles.passwordRow}>
              <TextInput
                value={password}
                onChangeText={(val) => {
                  setPassword(val);
                  setError('');
                }}
                style={[styles.textInput, { flex: 1 }]}
                secureTextEntry={!visible}
                accessibilityLabel="Mật mã"
                placeholder="Nhập mã truy cập"
                placeholderTextColor={C.muted}
              />
              <Pressable
                onPress={() => setVisible((v) => !v)}
                style={styles.showPassBtn}
                accessibilityRole="button"
              >
                <Text style={styles.showPassText}>{visible ? 'ẨN' : 'HIỆN'}</Text>
              </Pressable>
            </View>

            <SecurityNotice />

            {error ? <Text style={styles.errorText}>⚠ {error}</Text> : null}

            <View style={{ marginTop: 8 }}>
              <ActionBtn
                label={busy ? 'ĐANG KẾT NỐI…' : mode === 'live' ? 'ĐĂNG NHẬP BACKEND →' : 'ĐĂNG NHẬP HỆ THỐNG →'}
                onPress={submit}
                tone="primary"
                disabled={busy}
              />
              {busy && <ActivityIndicator style={{ marginTop: 8 }} color={C.cyan} />}
            </View>

            <View style={styles.footerNav}>
              {mode === 'mock' ? (
                <Pressable
                  onPress={() => actions.go('Register')}
                  style={styles.navLink}
                  accessibilityRole="button"
                >
                  <Text style={styles.navLinkText}>
                    Đăng ký tài khoản Sĩ quan trực ca (Operator) →
                  </Text>
                </Pressable>
              ) : (
                <Text style={styles.formSubtitle}>
                  Tài khoản LIVE do Admin tạo trên Backend (không tự đăng ký trên ứng dụng).
                </Text>
              )}
            </View>
          </Panel>
        </View>

        <Text style={styles.complianceNotice}>
          SMART VESSEL MOTION GUARD • PHÂN HỆ XÁC THỰC MOCK CONSOLE TV4
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/**
 * VIEW 2: Officer Register Screen
 */
export function RegisterScreen({ actions }: ScreenProps) {
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
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <View style={styles.cardWrapper}>
          <ReticleAccents />

          <Panel title="OFFICER ONBOARDING" tag="RBAC: TABLE 3.1">
            <Text style={styles.formTitle}>Đăng ký Sĩ quan</Text>
            <Text style={styles.formSubtitle}>
              Tạo tài khoản trực ca giám sát động học tàu mới:
            </Text>

            <Text style={styles.fieldLabel}>HỌ VÀ TÊN SĨ QUAN (FULL NAME)</Text>
            <TextInput
              value={fullName}
              onChangeText={(val) => {
                setFullName(val);
                setError('');
              }}
              style={styles.textInput}
              accessibilityLabel="Họ và tên"
              placeholder="e.g. Sĩ quan Nguyễn Văn A"
              placeholderTextColor={C.muted}
            />

            <Text style={styles.fieldLabel}>TÊN ĐĂNG NHẬP / MÃ SĨ QUAN (OFFICER ID)</Text>
            <TextInput
              value={username}
              onChangeText={(val) => {
                setUsername(val);
                setError('');
              }}
              style={styles.textInput}
              autoCapitalize="none"
              accessibilityLabel="Tên đăng nhập"
              placeholder="e.g. officer_bridge01"
              placeholderTextColor={C.muted}
            />

            <Text style={styles.fieldLabel}>MẬT KHẨU TRUY CẬP (PASSCODE)</Text>
            <View style={styles.passwordRow}>
              <TextInput
                value={password}
                onChangeText={(val) => {
                  setPassword(val);
                  setError('');
                }}
                style={[styles.textInput, { flex: 1 }]}
                secureTextEntry={!visible}
                accessibilityLabel="Mật khẩu"
                placeholder="Tối thiểu 6 ký tự"
                placeholderTextColor={C.muted}
              />
              <Pressable
                onPress={() => setVisible((v) => !v)}
                style={styles.showPassBtn}
                accessibilityRole="button"
              >
                <Text style={styles.showPassText}>{visible ? 'ẨN' : 'HIỆN'}</Text>
              </Pressable>
            </View>

            <Text style={styles.fieldLabel}>XÁC NHẬN MẬT KHẨU (CONFIRM PASSCODE)</Text>
            <TextInput
              value={confirmPassword}
              onChangeText={(val) => {
                setConfirmPassword(val);
                setError('');
              }}
              style={styles.textInput}
              secureTextEntry={!visible}
              accessibilityLabel="Xác nhận mật khẩu"
              placeholder="Nhập lại mật khẩu"
              placeholderTextColor={C.muted}
            />

            <View style={styles.roleLockBox}>
              <Text style={styles.roleLockTitle}>
                VAI TRÒ HỆ THỐNG: OPERATOR (SĨ QUAN TRỰC CA)
              </Text>
              <Text style={styles.roleLockText}>
                Quy chuẩn Bảng 3.1 Đề cương v2.0: Tài khoản tự đăng ký chỉ có quyền Sĩ quan trực ca (Operator / View-Only). Quyền Supervisor và Admin do Quản trị viên cấp phát riêng.
              </Text>
            </View>

            {error ? <Text style={styles.errorText}>⚠ {error}</Text> : null}

            {pendingNotice ? (
              <View style={styles.pendingNoticeBanner}>
                <Text style={styles.pendingNoticeTitle}>
                  THÔNG BÁO DỊCH VỤ XÁC THỰC:
                </Text>
                <Text style={styles.pendingNoticeText}>{pendingNotice}</Text>
                <View style={{ marginTop: 8 }}>
                  <ActionBtn
                    label="CHUYỂN SANG ĐĂNG NHẬP NGAY →"
                    onPress={() => actions.go('Login')}
                    tone="primary"
                  />
                </View>
              </View>
            ) : (
              <View style={{ marginTop: 8 }}>
                <ActionBtn
                  label="XÁC NHẬN ĐĂNG KÝ SĨ QUAN →"
                  onPress={submit}
                  tone="primary"
                />
              </View>
            )}

            <View style={styles.footerNav}>
              <Pressable
                onPress={() => actions.go('Login')}
                style={styles.navLink}
                accessibilityRole="button"
              >
                <Text style={styles.navLinkText}>← Quay lại Đăng nhập</Text>
              </Pressable>
            </View>
          </Panel>
        </View>

        <Text style={styles.complianceNotice}>
          HỆ THỐNG BẢO VỆ ĐỘNG HỌC TÀU • QUY CHUẨN AN TOÀN HÀNG HẢI
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/**
 * VIEW 3: Forgot Password / Key Recovery Screen
 */
export function ForgotPasswordScreen({ actions }: ScreenProps) {
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
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <BrandBanner />

        <View style={styles.cardWrapper}>
          <ReticleAccents />

          <Panel title="KEY RECOVERY PROTOCOL" tag="SYS_ID: 994-IMU-BRG">
            <Text style={styles.formTitle}>Khôi phục Mật mã</Text>
            <Text style={styles.formSubtitle}>
              Yêu cầu cấp lại mã truy cập buồng lái hoặc đặt lại mật mã:
            </Text>

            <Text style={styles.fieldLabel}>MÃ SĨ QUAN HOẶC EMAIL BUỒNG LÁI</Text>
            <TextInput
              value={identifier}
              onChangeText={(val) => {
                setIdentifier(val);
                setError('');
              }}
              style={styles.textInput}
              autoCapitalize="none"
              accessibilityLabel="Mã sĩ quan hoặc email"
              placeholder="e.g. operator hoặc officer.jensen@vessel01.bridge"
              placeholderTextColor={C.muted}
            />

            {error ? <Text style={styles.errorText}>⚠ {error}</Text> : null}

            {pendingNotice ? (
              <View style={styles.pendingNoticeBanner}>
                <Text style={styles.pendingNoticeTitle}>
                  TRẠNG THÁI HẠ TẦNG XÁC THỰC:
                </Text>
                <Text style={styles.pendingNoticeText}>{pendingNotice}</Text>
                <View style={{ marginTop: 8 }}>
                  <ActionBtn
                    label="QUAY LẠI MÀN HÌNH ĐĂNG NHẬP"
                    onPress={() => actions.go('Login')}
                    tone="primary"
                  />
                </View>
              </View>
            ) : (
              <View style={{ marginTop: 8 }}>
                <ActionBtn
                  label="GỬI YÊU CẦU ĐẶT LẠI MẬT MÃ →"
                  onPress={submit}
                  tone="primary"
                />
              </View>
            )}

            <View style={styles.footerNav}>
              <Pressable
                onPress={() => actions.go('Login')}
                style={styles.navLink}
                accessibilityRole="button"
              >
                <Text style={styles.navLinkText}>← Quay lại Đăng nhập</Text>
              </Pressable>
            </View>
          </Panel>
        </View>

        <Text style={styles.complianceNotice}>
          CƠ CHẾ BẢO MẬT PHẦN CỨNG • THỦ TỤC CẤP PHÁT THẺ RSA-4096
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.canvas,
  },
  scrollContent: {
    paddingHorizontal: 14,
    paddingTop: 16,
    paddingBottom: 24,
    gap: 12,
  },
  brandWell: {
    backgroundColor: C.panel,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderColor: C.borderSubtle,
    borderLeftColor: C.borderNavy,
    borderRadius: 14,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    ...SHADOWS.card,
  },
  brandIconBox: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#EAF2FA',
    borderWidth: 1,
    borderColor: C.borderSubtle,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandIcon: {
    color: C.cyan,
    fontSize: 26,
    fontWeight: '800',
  },
  brandTextCol: {
    flex: 1,
  },
  brandEyebrow: {
    color: C.cyanBright,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  brandTitle: {
    color: C.text,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.3,
    marginTop: 1,
  },
  brandSub: {
    color: C.muted,
    fontSize: 10,
    marginTop: 2,
  },
  cardWrapper: {
    position: 'relative',
  },
  reticleTL: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: 12,
    height: 12,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderColor: C.cyan,
    zIndex: 10,
  },
  reticleTR: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 12,
    height: 12,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderColor: C.cyan,
    zIndex: 10,
  },
  reticleBL: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: 12,
    height: 12,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderColor: C.cyan,
    zIndex: 10,
  },
  reticleBR: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 12,
    height: 12,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderColor: C.cyan,
    zIndex: 10,
  },
  formTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: C.text,
    marginTop: 2,
  },
  formSubtitle: {
    fontSize: 11,
    color: C.muted,
    marginTop: 2,
    marginBottom: 6,
  },
  fieldLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginTop: 6,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  keyRecoveryText: {
    color: C.cyan,
    fontSize: 10,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
  textInput: {
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#FFFFFF',
    color: C.text,
    fontSize: 14,
    minHeight: 44,
    marginTop: 2,
  },
  passwordRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    marginTop: 2,
  },
  showPassBtn: {
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 8,
    backgroundColor: C.panelHigh,
    paddingHorizontal: 12,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  showPassText: {
    color: C.cyan,
    fontSize: 11,
    fontWeight: '800',
  },
  secNoticeBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(2, 132, 199, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(2, 132, 199, 0.25)',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginTop: 10,
  },
  secNoticeIcon: {
    fontSize: 12,
  },
  secNoticeText: {
    color: C.text,
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  roleLockBox: {
    backgroundColor: '#EAF2FA',
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderColor: C.borderSubtle,
    borderLeftColor: C.borderNavy,
    borderRadius: 10,
    padding: 10,
    marginTop: 10,
    gap: 3,
  },
  roleLockTitle: {
    color: C.text,
    fontSize: 11,
    fontWeight: '800',
  },
  roleLockText: {
    color: C.muted,
    fontSize: 10,
    lineHeight: 14,
  },
  pendingNoticeBanner: {
    backgroundColor: 'rgba(217, 119, 6, 0.1)',
    borderWidth: 1,
    borderColor: '#D97706',
    borderRadius: 12,
    padding: 12,
    marginTop: 10,
    gap: 4,
    ...SHADOWS.warningGlow,
  },
  pendingNoticeTitle: {
    color: '#B45309',
    fontSize: 11,
    fontWeight: '800',
  },
  pendingNoticeText: {
    color: C.text,
    fontSize: 10.5,
    lineHeight: 15,
  },
  errorText: {
    color: C.red,
    fontSize: 12,
    fontWeight: '600',
    marginTop: 6,
  },
  footerNav: {
    borderTopWidth: 1,
    borderTopColor: C.borderSubtle,
    marginTop: 12,
    paddingTop: 10,
    alignItems: 'center',
  },
  navLink: {
    paddingVertical: 4,
  },
  navLinkText: {
    color: C.text,
    fontSize: 11,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
  complianceNotice: {
    color: C.muted,
    fontSize: 9.5,
    textAlign: 'center',
    marginTop: 2,
  },
});
