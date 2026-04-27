import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NgIf } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgIf],
  template: `
    <div class="min-h-screen bg-slate-950 text-white flex">

      <!-- Sidebar -->
      <aside class="w-60 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">

        <!-- Logo -->
        <div class="px-5 py-5 border-b border-slate-800 flex items-center gap-3">
          <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
          </div>
          <span class="font-bold text-base tracking-tight">Polish Bank</span>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 px-3 py-4 space-y-1">
          <a routerLink="/dashboard" routerLinkActive="nav-active" [routerLinkActiveOptions]="{exact:true}"
             class="nav-item">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Pulpit
          </a>

          <a routerLink="/settings" routerLinkActive="nav-active"
             class="nav-item">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0
                   002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0
                   001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0
                   00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0
                   00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0
                   00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0
                   00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0
                   001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07
                   2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Ustawienia
          </a>
        </nav>

        <!-- User + logout -->
        <div class="px-3 py-4 border-t border-slate-800">
          <div *ngIf="user()" class="px-3 py-2 mb-2">
            <p class="text-sm font-medium text-white truncate">{{ user()!.first_name }} {{ user()!.last_name }}</p>
            <p class="text-xs text-slate-500 truncate">{{ user()!.email }}</p>
          </div>
          <button (click)="logout()"
                  class="nav-item w-full text-red-400 hover:text-red-300 hover:bg-red-950/40">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Wyloguj
          </button>
        </div>
      </aside>

      <!-- Main -->
      <div class="flex-1 flex flex-col min-w-0">

        <!-- Header -->
        <header class="border-b border-slate-800 bg-slate-900/50 px-6 py-3 flex items-center justify-between flex-shrink-0">
          <h1 class="text-sm font-semibold text-slate-400 tracking-wide uppercase">
            {{ pageTitle() }}
          </h1>
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            System aktywny
          </div>
        </header>

        <!-- Content -->
        <main class="flex-1 overflow-y-auto">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
  styles: [`
    .nav-item {
      @apply flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400
             hover:text-white hover:bg-slate-800 transition-colors duration-150 cursor-pointer;
    }
    .nav-active {
      @apply text-white bg-slate-800;
    }
  `],
})
export class LayoutComponent {
  private auth = inject(AuthService);
  readonly user = this.auth.user;

  pageTitle() {
    const path = window.location.pathname;
    if (path.includes('settings')) return 'Ustawienia';
    if (path.includes('dashboard')) return 'Pulpit';
    return 'Polish Bank';
  }

  logout() { this.auth.logout(); }
}
