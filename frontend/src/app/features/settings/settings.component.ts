import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl } from '@angular/forms';
import { NgFor, NgIf, DecimalPipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { PhoneAlias, P2pService } from '../../core/services/p2p.service';
import { Account } from '../dashboard/dashboard.component';

function passwordMatchValidator(group: AbstractControl) {
  const pw = group.get('new_password')?.value;
  const pc = group.get('new_password_confirm')?.value;
  return pw && pc && pw !== pc ? { mismatch: true } : null;
}

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [ReactiveFormsModule, NgFor, NgIf, DecimalPipe],
  templateUrl: './settings.component.html',
})
export class SettingsComponent implements OnInit {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private p2p = inject(P2pService);
  private fb = inject(FormBuilder);

  readonly user = this.auth.user;
  readonly isJunior = computed(() => this.user()?.role === 'JUNIOR');

  accounts = signal<Account[]>([]);
  aliases = signal<PhoneAlias[]>([]);
  loadingAccounts = signal(true);
  aliasLoading = signal(false);
  aliasError = signal('');
  aliasSuccess = signal('');

  copiedIban = signal('');

  topUpAmounts = signal<Record<string, string>>({});
  topUpLoading = signal('');
  topUpSuccess = signal('');
  topUpError = signal('');

  profileLoading = signal(false);
  profileSuccess = signal('');
  profileError = signal('');

  passwordLoading = signal(false);
  passwordSuccess = signal('');
  passwordError = signal('');

  profileForm = this.fb.group({
    first_name: [''],
    last_name: [''],
    phone_number: [''],
  });

  passwordForm = this.fb.group(
    {
      old_password: ['', Validators.required],
      new_password: ['', [Validators.required, Validators.minLength(8)]],
      new_password_confirm: ['', Validators.required],
    },
    { validators: passwordMatchValidator },
  );

  aliasForm = this.fb.group({
    phone: [''],
  });

  ngOnInit() {
    const user = this.auth.user();
    if (user) {
      this.profileForm.patchValue({
        first_name: user.first_name,
        last_name: user.last_name,
        phone_number: user.phone_number,
      });
    }
    this.loadAccounts();
    if (this.isJunior()) this.loadAliases();
  }

  juniorAccount() {
    return this.accounts().find((a) => a.account_type === 'JUNIOR') || null;
  }

  juniorAlias() {
    const acc = this.juniorAccount();
    if (!acc) return null;
    return this.aliases().find((alias) => alias.account === acc.id) || null;
  }

  loadAliases() {
    this.p2p.listAliases().subscribe((aliases) => this.aliases.set(aliases));
  }

  registerAlias() {
    const account = this.juniorAccount();
    if (!account) return;

    this.aliasLoading.set(true);
    this.aliasError.set('');
    this.aliasSuccess.set('');

    const phone = (this.aliasForm.value.phone as string) || undefined;
    this.p2p.registerAlias({ account_id: account.id, phone }).subscribe({
      next: () => {
        this.aliasLoading.set(false);
        this.aliasSuccess.set('Numer połączony z kontem — możesz dostawać przelewy BLIK/KLIK.');
        this.aliasForm.patchValue({ phone: '' });
        this.loadAliases();
        setTimeout(() => this.aliasSuccess.set(''), 5000);
      },
      error: (err) => {
        this.aliasLoading.set(false);
        this.aliasError.set(this.extractError(err, 'Nie udało się połączyć numeru.'));
      },
    });
  }

  deleteAlias(alias: PhoneAlias) {
    this.aliasError.set('');
    this.p2p.deleteAlias(alias.phone).subscribe({
      next: () => {
        this.aliasSuccess.set('Numer odłączony od konta.');
        this.loadAliases();
        setTimeout(() => this.aliasSuccess.set(''), 4000);
      },
      error: (err) => this.aliasError.set(this.extractError(err, 'Nie udało się odłączyć numeru.')),
    });
  }

  private extractError(err: any, fallback: string) {
    const data = err?.error;
    if (data?.detail) return data.detail;
    if (typeof data === 'object' && data) return Object.values(data).flat().join(' ');
    return fallback;
  }

  private loadAccounts() {
    this.loadingAccounts.set(true);
    this.http.get<Account[]>('/api/accounts/').subscribe({
      next: (accs) => { this.accounts.set(accs); this.loadingAccounts.set(false); },
      error: () => this.loadingAccounts.set(false),
    });
  }

  formatIban(iban: string): string {
    return iban.replace(/(.{4})/g, '$1 ').trim();
  }

  copyIban(iban: string) {
    navigator.clipboard.writeText(iban).then(() => {
      this.copiedIban.set(iban);
      setTimeout(() => this.copiedIban.set(''), 2000);
    });
  }

  setTopUpAmount(accountId: string, event: Event) {
    const value = (event.target as HTMLInputElement).value;
    this.topUpAmounts.update((amounts) => ({ ...amounts, [accountId]: value }));
  }

  topUp(accountId: string) {
    const raw = this.topUpAmounts()[accountId];
    const amount = parseFloat(raw ?? '');
    if (!amount || amount <= 0) return;

    this.topUpLoading.set(accountId);
    this.topUpSuccess.set('');
    this.topUpError.set('');

    this.http.post<Account>(`/api/accounts/${accountId}/top-up/`, { amount }).subscribe({
      next: () => {
        this.topUpLoading.set('');
        this.topUpSuccess.set(accountId);
        this.topUpAmounts.update((amounts) => ({ ...amounts, [accountId]: '' }));
        this.loadAccounts();
        setTimeout(() => this.topUpSuccess.set(''), 3000);
      },
      error: () => {
        this.topUpLoading.set('');
        this.topUpError.set(accountId);
        setTimeout(() => this.topUpError.set(''), 3000);
      },
    });
  }

  saveProfile() {
    this.profileLoading.set(true);
    this.profileSuccess.set('');
    this.profileError.set('');

    this.http.patch('/api/auth/me/', this.profileForm.value).subscribe({
      next: () => {
        this.profileLoading.set(false);
        this.profileSuccess.set('Dane zostały zaktualizowane.');
        setTimeout(() => this.profileSuccess.set(''), 4000);
      },
      error: (err) => {
        this.profileLoading.set(false);
        const data = err?.error;
        this.profileError.set(
          typeof data === 'object' ? Object.values(data).flat().join(' ') : 'Błąd zapisu.',
        );
      },
    });
  }

  changePassword() {
    if (this.passwordForm.invalid) return;
    this.passwordLoading.set(true);
    this.passwordSuccess.set('');
    this.passwordError.set('');

    const { old_password, new_password } = this.passwordForm.value as {
      old_password: string;
      new_password: string;
    };

    this.http.post('/api/auth/change-password/', { old_password, new_password }).subscribe({
      next: () => {
        this.passwordLoading.set(false);
        this.passwordSuccess.set('Hasło zostało zmienione pomyślnie.');
        this.passwordForm.reset();
        setTimeout(() => this.passwordSuccess.set(''), 5000);
      },
      error: (err) => {
        this.passwordLoading.set(false);
        const data = err?.error;
        this.passwordError.set(
          typeof data === 'object' ? Object.values(data).flat().join(' ') : 'Błąd zmiany hasła.',
        );
      },
    });
  }
}