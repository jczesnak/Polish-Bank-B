import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators, AbstractControl } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgIf, KeyValuePipe } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';

function peselValidator(control: AbstractControl) {
  const v = control.value as string;
  if (!v) return null;
  return /^\d{11}$/.test(v) ? null : { pesel: true };
}

function passwordMatchValidator(group: AbstractControl) {
  const pw = group.get('password')?.value;
  const pc = group.get('password_confirm')?.value;
  return pw && pc && pw !== pc ? { mismatch: true } : null;
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, NgIf],
  template: `
    <div class="min-h-screen bg-slate-950 flex items-center justify-center p-4 py-10">
      <div class="w-full max-w-md">

        <!-- Logo -->
        <div class="text-center mb-8">
          <div class="inline-flex items-center gap-3 mb-3">
            <div class="w-11 h-11 bg-indigo-600 rounded-xl flex items-center justify-center">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <span class="text-white text-2xl font-bold tracking-tight">Polish Bank</span>
          </div>
          <p class="text-slate-400 text-sm">Utwórz nowe konto bankowe</p>
        </div>

        <!-- Card -->
        <div class="card p-8">
          <form [formGroup]="form" (ngSubmit)="onSubmit()">

            <!-- Row: imię / nazwisko -->
            <div class="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label class="label">Imię</label>
                <input formControlName="first_name" type="text" class="input-field" placeholder="Jan" />
                <p *ngIf="form.get('first_name')?.touched && form.get('first_name')?.invalid"
                   class="mt-1 text-xs text-red-400">Wymagane.</p>
              </div>
              <div>
                <label class="label">Nazwisko</label>
                <input formControlName="last_name" type="text" class="input-field" placeholder="Kowalski" />
                <p *ngIf="form.get('last_name')?.touched && form.get('last_name')?.invalid"
                   class="mt-1 text-xs text-red-400">Wymagane.</p>
              </div>
            </div>

            <div class="mb-4">
              <label class="label">Adres email</label>
              <input formControlName="email" type="email" class="input-field"
                     placeholder="jan.kowalski@example.com" autocomplete="email" />
              <p *ngIf="form.get('email')?.touched && form.get('email')?.invalid"
                 class="mt-1 text-xs text-red-400">Podaj prawidłowy email.</p>
            </div>

            <div class="mb-4">
              <label class="label">PESEL</label>
              <input formControlName="pesel" type="text" class="input-field"
                     placeholder="12345678901" maxlength="11" />
              <p *ngIf="form.get('pesel')?.touched && form.get('pesel')?.hasError('pesel')"
                 class="mt-1 text-xs text-red-400">PESEL musi składać się z 11 cyfr.</p>
            </div>

            <div class="mb-4">
              <label class="label">Numer telefonu</label>
              <input formControlName="phone_number" type="tel" class="input-field"
                     placeholder="+48 123 456 789" />
            </div>

            <div class="mb-4">
              <label class="label">Hasło</label>
              <input formControlName="password" type="password" class="input-field"
                     placeholder="Min. 8 znaków" autocomplete="new-password" />
              <p *ngIf="form.get('password')?.touched && form.get('password')?.hasError('minlength')"
                 class="mt-1 text-xs text-red-400">Hasło musi mieć co najmniej 8 znaków.</p>
            </div>

            <div class="mb-6">
              <label class="label">Potwierdź hasło</label>
              <input formControlName="password_confirm" type="password" class="input-field"
                     placeholder="••••••••" autocomplete="new-password" />
              <p *ngIf="form.get('password_confirm')?.touched && form.hasError('mismatch')"
                 class="mt-1 text-xs text-red-400">Hasła nie są identyczne.</p>
            </div>

            <div *ngIf="error()" class="mb-4 p-3 bg-red-950/60 border border-red-900 rounded-lg text-red-400 text-sm">
              {{ error() }}
            </div>

            <button
              type="submit"
              [disabled]="loading() || form.invalid"
              class="btn-primary w-full flex items-center justify-center gap-2 text-base"
            >
              <svg *ngIf="loading()" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ loading() ? 'Tworzenie konta...' : 'Zarejestruj się' }}
            </button>
          </form>

          <p class="text-center text-slate-400 text-sm mt-6">
            Masz już konto?
            <a routerLink="/auth/login" class="text-indigo-400 hover:text-indigo-300 font-medium ml-1">
              Zaloguj się
            </a>
          </p>
        </div>

      </div>
    </div>
  `,
})
export class RegisterComponent {
  form = this.fb.group(
    {
      first_name: ['', Validators.required],
      last_name: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      pesel: ['', peselValidator],
      phone_number: [''],
      password: ['', [Validators.required, Validators.minLength(8)]],
      password_confirm: ['', Validators.required],
    },
    { validators: passwordMatchValidator },
  );

  loading = signal(false);
  error = signal('');

  constructor(private fb: FormBuilder, private auth: AuthService) {}

  onSubmit() {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');

    const v = this.form.value as {
      first_name: string; last_name: string; email: string;
      pesel: string; phone_number: string; password: string; password_confirm: string;
    };

    this.auth.register(v).subscribe({
      next: () => this.loading.set(false),
      error: (err) => {
        this.loading.set(false);
        const data = err?.error;
        if (typeof data === 'object') {
          const msgs = Object.values(data).flat().join(' ');
          this.error.set(msgs);
        } else {
          this.error.set('Błąd rejestracji. Spróbuj ponownie.');
        }
      },
    });
  }
}
