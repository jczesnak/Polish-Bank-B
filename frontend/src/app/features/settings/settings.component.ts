import { Component, OnInit, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl } from '@angular/forms';
import { NgFor, NgIf, DecimalPipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
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
  private fb = inject(FormBuilder);

  accounts = signal<Account[]>([]);
  loadingAccounts = signal(true);

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

  pinSetupForm = this.fb.group({ pin: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]] });
  pinSetupLoading = signal(false);
  pinSetupSuccess = signal('');
  pinSetupError = signal('');

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

  submitPinSetup() {
    if (this.pinSetupForm.invalid) return;
    this.pinSetupLoading.set(true);
    this.pinSetupError.set('');
    this.pinSetupSuccess.set('');

    this.http.post('/api/auth/pin/', this.pinSetupForm.value).subscribe({
      next: () => {
        this.pinSetupLoading.set(false);
        this.pinSetupSuccess.set('PIN BLIK został pomyślnie ustawiony/zmieniony.');
        this.pinSetupForm.reset();
        setTimeout(() => this.pinSetupSuccess.set(''), 5000);
      },
      error: (err) => {
        this.pinSetupLoading.set(false);
        this.pinSetupError.set(err.error?.pin || err.error?.detail || 'Błąd ustawiania PINu.');
      }
    });
  }
}