// Compatibility tables and VS 2022 constexpr std::mutex / std::condition_variable
// runtime implementation for linking VS 2022 precompiled objects on VS 2019 build tools.

#include <yvals_core.h>
#include <cstdint>

#define inline extern __declspec(selectany)
#define constexpr const
#include <xcharconv_ryu_tables.h>
#undef constexpr
#undef inline

#define _General_precision_tables _General_precision_tables_2
#include <charconv>
#undef _General_precision_tables

namespace std {
    constexpr uint32_t _General_precision_tables_2<float>::_Special_X_table[63];
    constexpr uint32_t _General_precision_tables_2<float>::_Ordinary_X_table[44];
    constexpr uint64_t _General_precision_tables_2<double>::_Special_X_table[195];
    constexpr uint64_t _General_precision_tables_2<double>::_Ordinary_X_table[314];
}

extern "C" const void* const __msvc_compat_keep_tables[] = {
    std::__DOUBLE_POW5_INV_SPLIT,
    std::__DOUBLE_POW5_SPLIT,
    std::__POW10_SPLIT,
    std::__POW10_SPLIT_2,
    std::_General_precision_tables_2<float>::_Special_X_table,
    std::_General_precision_tables_2<float>::_Ordinary_X_table,
    std::_General_precision_tables_2<double>::_Special_X_table,
    std::_General_precision_tables_2<double>::_Ordinary_X_table,
};

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <xthreads.h>
#include <xtimec.h>
#include <windows.h>

enum class __stl_sync_api_modes_enum { normal, win7, vista, concrt };
__stl_sync_api_modes_enum __stl_sync_api_impl_mode = __stl_sync_api_modes_enum::normal;

struct _Mtx_internal_imp_t {
    int type;
    void* vptr_unused;
    SRWLOCK srw_lock;
    unsigned char pad[64 - 2 * sizeof(void*)];
    long thread_id;
    int count;
};

struct _Cnd_internal_imp_t {
    void* vptr_unused;
    CONDITION_VARIABLE cv;
    unsigned char pad[72 - 2 * sizeof(void*)];
};

static_assert(sizeof(_Mtx_internal_imp_t) == 80, "incorrect _Mtx_internal_imp_t size");
static_assert(sizeof(_Cnd_internal_imp_t) == 72, "incorrect _Cnd_internal_imp_t size");

extern "C" {

void __cdecl _Thrd_abort(const char* msg) {
    fputs(msg, stderr);
    fputc('\n', stderr);
    abort();
}

void __cdecl __set_stl_sync_api_mode(__stl_sync_api_modes_enum mode) {
    __stl_sync_api_impl_mode = mode;
}

void __cdecl _Mtx_init_in_situ(_Mtx_t mtx, int type) {
    mtx->vptr_unused = nullptr;
    InitializeSRWLock(&mtx->srw_lock);
    mtx->thread_id = -1;
    mtx->type = type;
    mtx->count = 0;
}

void __cdecl _Mtx_destroy_in_situ(_Mtx_t mtx) {
    (void)mtx;
}

int __cdecl _Mtx_init(_Mtx_t* mtx, int type) {
    *mtx = nullptr;
    _Mtx_t mutex = static_cast<_Mtx_t>(calloc(1, sizeof(_Mtx_internal_imp_t)));
    if (mutex == nullptr) {
        return _Thrd_nomem;
    }
    _Mtx_init_in_situ(mutex, type);
    *mtx = mutex;
    return _Thrd_success;
}

void __cdecl _Mtx_destroy(_Mtx_t mtx) {
    if (mtx) {
        _Mtx_destroy_in_situ(mtx);
        free(mtx);
    }
}

static int mtx_do_lock(_Mtx_t mtx, const xtime* target) {
    const long current_tid = static_cast<long>(GetCurrentThreadId());
    if ((mtx->type & ~_Mtx_recursive) == _Mtx_plain) {
        if (mtx->thread_id != current_tid) {
            AcquireSRWLockExclusive(&mtx->srw_lock);
            mtx->thread_id = current_tid;
        }
        ++mtx->count;
        return _Thrd_success;
    } else {
        int res = WAIT_TIMEOUT;
        if (target == nullptr) {
            if (mtx->thread_id != current_tid) {
                AcquireSRWLockExclusive(&mtx->srw_lock);
            }
            res = WAIT_OBJECT_0;
        } else if (target->sec < 0 || (target->sec == 0 && target->nsec <= 0)) {
            if (mtx->thread_id != current_tid) {
                if (TryAcquireSRWLockExclusive(&mtx->srw_lock) != 0) {
                    res = WAIT_OBJECT_0;
                } else {
                    res = WAIT_TIMEOUT;
                }
            } else {
                res = WAIT_OBJECT_0;
            }
        } else {
            xtime now;
            xtime_get(&now, TIME_UTC);
            while (now.sec < target->sec || (now.sec == target->sec && now.nsec < target->nsec)) {
                if (mtx->thread_id == current_tid || TryAcquireSRWLockExclusive(&mtx->srw_lock) != 0) {
                    res = WAIT_OBJECT_0;
                    break;
                }
                xtime_get(&now, TIME_UTC);
            }
        }

        if (res == WAIT_OBJECT_0 || res == WAIT_ABANDONED) {
            if (1 < ++mtx->count) {
                if ((mtx->type & _Mtx_recursive) != _Mtx_recursive) {
                    --mtx->count;
                    res = WAIT_TIMEOUT;
                }
            } else {
                mtx->thread_id = current_tid;
            }
        }

        switch (res) {
        case WAIT_OBJECT_0:
        case WAIT_ABANDONED:
            return _Thrd_success;
        case WAIT_TIMEOUT:
            if (target == nullptr || (target->sec == 0 && target->nsec == 0)) {
                return _Thrd_busy;
            } else {
                return _Thrd_timedout;
            }
        default:
            return _Thrd_error;
        }
    }
}

int __cdecl _Mtx_unlock(_Mtx_t mtx) {
    if (--mtx->count == 0) {
        mtx->thread_id = -1;
        ReleaseSRWLockExclusive(&mtx->srw_lock);
    }
    return _Thrd_success;
}

int __cdecl _Mtx_lock(_Mtx_t mtx) {
    return mtx_do_lock(mtx, nullptr);
}

int __cdecl _Mtx_trylock(_Mtx_t mtx) {
    xtime xt;
    xt.sec = 0;
    xt.nsec = 0;
    return mtx_do_lock(mtx, &xt);
}

int __cdecl _Mtx_timedlock(_Mtx_t mtx, const xtime* xt) {
    int res = mtx_do_lock(mtx, xt);
    return res == _Thrd_busy ? _Thrd_timedout : res;
}

int __cdecl _Mtx_current_owns(_Mtx_t mtx) {
    return mtx->count != 0 && mtx->thread_id == static_cast<long>(GetCurrentThreadId());
}

void* __cdecl _Mtx_getconcrtcs(_Mtx_t mtx) {
    return &mtx->vptr_unused;
}

void __cdecl _Mtx_clear_owner(_Mtx_t mtx) {
    mtx->thread_id = -1;
    --mtx->count;
}

void __cdecl _Mtx_reset_owner(_Mtx_t mtx) {
    mtx->thread_id = static_cast<long>(GetCurrentThreadId());
    ++mtx->count;
}

void __cdecl _Cnd_init_in_situ(_Cnd_t cond) {
    cond->vptr_unused = nullptr;
    InitializeConditionVariable(&cond->cv);
}

void __cdecl _Cnd_destroy_in_situ(_Cnd_t cond) {
    (void)cond;
}

int __cdecl _Cnd_init(_Cnd_t* pcond) {
    *pcond = nullptr;
    _Cnd_t cond = static_cast<_Cnd_t>(calloc(1, sizeof(_Cnd_internal_imp_t)));
    if (cond == nullptr) {
        return _Thrd_nomem;
    }
    _Cnd_init_in_situ(cond);
    *pcond = cond;
    return _Thrd_success;
}

void __cdecl _Cnd_destroy(_Cnd_t cond) {
    if (cond) {
        _Cnd_destroy_in_situ(cond);
        free(cond);
    }
}

int __cdecl _Cnd_wait(_Cnd_t cond, _Mtx_t mtx) {
    _Mtx_clear_owner(mtx);
    if (!SleepConditionVariableSRW(&cond->cv, &mtx->srw_lock, INFINITE, 0)) {
        abort();
    }
    _Mtx_reset_owner(mtx);
    return _Thrd_success;
}

int __cdecl _Cnd_timedwait(_Cnd_t cond, _Mtx_t mtx, const xtime* target) {
    int res = _Thrd_success;
    if (target == nullptr) {
        _Mtx_clear_owner(mtx);
        if (!SleepConditionVariableSRW(&cond->cv, &mtx->srw_lock, INFINITE, 0)) {
            abort();
        }
        _Mtx_reset_owner(mtx);
    } else {
        xtime now;
        xtime_get(&now, TIME_UTC);
        _Mtx_clear_owner(mtx);
        if (!SleepConditionVariableSRW(&cond->cv, &mtx->srw_lock, _Xtime_diff_to_millis2(target, &now), 0)) {
            xtime_get(&now, TIME_UTC);
            if (_Xtime_diff_to_millis2(target, &now) == 0) {
                res = _Thrd_timedout;
            }
        }
        _Mtx_reset_owner(mtx);
    }
    return res;
}

int __cdecl _Cnd_signal(_Cnd_t cond) {
    WakeConditionVariable(&cond->cv);
    return _Thrd_success;
}

int __cdecl _Cnd_broadcast(_Cnd_t cond) {
    WakeAllConditionVariable(&cond->cv);
    return _Thrd_success;
}

} // extern "C"
