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
  templateUrl: './register.component.html',
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