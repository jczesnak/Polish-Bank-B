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
  template: `
    <div class="text-white">
      <main class="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">

        <h1 class="text-2xl font-bold">Ustawienia konta</h1>

        <!-- ===== Rachunki ===== -->
        <div class="card p-6">
          <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-5">
            Twoje rachunki
          </h2>

          <div *ngIf="loadingAccounts()" class="space-y-3">
            <div *ngFor="let i of [1, 2]" class="h-24 bg-slate-800 rounded-xl animate-pulse"></div>
          </div>

          <div *ngIf="!loadingAccounts()" class="space-y-4">
            <div *ngFor="let acc of accounts()"
                 class="bg-slate-800/50 border border-slate-700 rounded-xl p-4">

              <!-- Header -->
              <div class="flex items-start justify-between mb-3">
                <div>
                  <p class="font-semibold text-white">{{ acc.account_type_display }}</p>
                  <p class="text-xs text-slate-400 mt-0.5">
                    Saldo:
                    <span class="text-white font-medium">
                      {{ acc.balance | number:'1.2-2' }} PLN
                    </span>
                  </p>
                </div>
                <span class="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded-full">
                  {{ acc.currency }}
                </span>
              </div>

              <!-- IBAN -->
              <div class="bg-slate-900 rounded-lg px-3 py-2.5 mb-4 flex items-center justify-between gap-3">
                <span class="text-sm font-mono text-slate-300 tracking-wider break-all">
                  {{ formatIban(acc.iban) }}
                </span>
                <button (click)="copyIban(acc.iban)"
                        class="text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex-shrink-0">
                  {{ copiedIban() === acc.iban ? '✓ Skopiowano' : 'Kopiuj' }}
                </button>
              </div>

              <!-- Top-up -->
              <div class="flex items-center gap-2">
                <input
                  type="number"
                  step="100"
                  min="1"
                  placeholder="Kwota doładowania (PLN)"
                  class="input-field text-sm py-2 flex-1"
                  [value]="topUpAmounts()[acc.id] ?? ''"
                  (input)="setTopUpAmount(acc.id, $event)"
                />
                <button
                  (click)="topUp(acc.id)"
                  [disabled]="topUpLoading() === acc.id"
                  class="btn-secondary text-sm py-2 px-4 whitespace-nowrap flex-shrink-0 flex items-center gap-1.5">
                  <svg *ngIf="topUpLoading() === acc.id"
                       class="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  {{ topUpLoading() === acc.id ? 'Doładowuję...' : '+ Doładuj' }}
                </button>
              </div>

              <p *ngIf="topUpSuccess() === acc.id"
                 class="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                ✓ Doładowanie zakończone pomyślnie.
              </p>
              <p *ngIf="topUpError() === acc.id"
                 class="text-xs text-red-400 mt-2">
                Błąd doładowania. Upewnij się, że kwota jest poprawna.
              </p>
            </div>

            <div *ngIf="accounts().length === 0" class="text-slate-500 text-sm text-center py-6">
              Brak rachunków
            </div>
          </div>
        </div>

        <!-- ===== Dane osobowe ===== -->
        <div class="card p-6">
          <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-5">
            Dane osobowe
          </h2>
          <form [formGroup]="profileForm" (ngSubmit)="saveProfile()">
            <div class="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label class="label">Imię</label>
                <input formControlName="first_name" type="text" class="input-field" />
              </div>
              <div>
                <label class="label">Nazwisko</label>
                <input formControlName="last_name" type="text" class="input-field" />
              </div>
            </div>
            <div class="mb-6">
              <label class="label">Numer telefonu</label>
              <input formControlName="phone_number" type="tel" class="input-field"
                     placeholder="+48 123 456 789" />
            </div>

            <div *ngIf="profileSuccess()"
                 class="mb-4 p-3 bg-emerald-950/60 border border-emerald-900 rounded-lg text-emerald-400 text-sm">
              {{ profileSuccess() }}
            </div>
            <div *ngIf="profileError()"
                 class="mb-4 p-3 bg-red-950/60 border border-red-900 rounded-lg text-red-400 text-sm">
              {{ profileError() }}
            </div>

            <button type="submit" [disabled]="profileLoading()" class="btn-primary">
              {{ profileLoading() ? 'Zapisywanie...' : 'Zapisz zmiany' }}
            </button>
          </form>
        </div>

        <!-- ===== Zmiana hasła ===== -->
        <div class="card p-6">
          <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-5">
            Zmiana hasła
          </h2>
          <form [formGroup]="passwordForm" (ngSubmit)="changePassword()">
            <div class="mb-4">
              <label class="label">Aktualne hasło</label>
              <input formControlName="old_password" type="password" class="input-field"
                     placeholder="••••••••" autocomplete="current-password" />
            </div>
            <div class="mb-4">
              <label class="label">Nowe hasło</label>
              <input formControlName="new_password" type="password" class="input-field"
                     placeholder="Min. 8 znaków" autocomplete="new-password" />
              <p *ngIf="passwordForm.get('new_password')?.touched && passwordForm.get('new_password')?.hasError('minlength')"
                 class="mt-1 text-xs text-red-400">Hasło musi mieć co najmniej 8 znaków.</p>
            </div>
            <div class="mb-6">
              <label class="label">Potwierdź nowe hasło</label>
              <input formControlName="new_password_confirm" type="password" class="input-field"
                     placeholder="••••••••" autocomplete="new-password" />
              <p *ngIf="passwordForm.get('new_password_confirm')?.touched && passwordForm.hasError('mismatch')"
                 class="mt-1 text-xs text-red-400">Hasła nie są identyczne.</p>
            </div>

            <div *ngIf="passwordSuccess()"
                 class="mb-4 p-3 bg-emerald-950/60 border border-emerald-900 rounded-lg text-emerald-400 text-sm">
              {{ passwordSuccess() }}
            </div>
            <div *ngIf="passwordError()"
                 class="mb-4 p-3 bg-red-950/60 border border-red-900 rounded-lg text-red-400 text-sm">
              {{ passwordError() }}
            </div>

            <button type="submit" [disabled]="passwordLoading() || passwordForm.invalid" class="btn-primary">
              {{ passwordLoading() ? 'Zmienianie...' : 'Zmień hasło' }}
            </button>
          </form>
        </div>

      </main>
    </div>
  `,
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
}
