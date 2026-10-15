// Compatibility tables for MSVC STL floating-point formatting
// required when linking VS 2022 precompiled objects on VS 2019 build tools.

namespace std {
    typedef unsigned __int64 uint64_t;
    typedef unsigned int uint32_t;

    extern const uint64_t __DOUBLE_POW5_INV_SPLIT[292][2];
    const uint64_t __DOUBLE_POW5_INV_SPLIT[292][2] = {0};

    extern const uint64_t __DOUBLE_POW5_SPLIT[326][2];
    const uint64_t __DOUBLE_POW5_SPLIT[326][2] = {0};

    extern const uint64_t __POW10_SPLIT[1224][3];
    const uint64_t __POW10_SPLIT[1224][3] = {0};

    extern const uint64_t __POW10_SPLIT_2[3133][3];
    const uint64_t __POW10_SPLIT_2[3133][3] = {0};

    template <class T> struct _General_precision_tables_2;

    template <> struct _General_precision_tables_2<float> {
        static const uint32_t _Special_X_table[1];
        static const uint32_t _Ordinary_X_table[1];
    };
    const uint32_t _General_precision_tables_2<float>::_Special_X_table[1] = {0};
    const uint32_t _General_precision_tables_2<float>::_Ordinary_X_table[1] = {0};

    template <> struct _General_precision_tables_2<double> {
        static const uint64_t _Special_X_table[1];
        static const uint64_t _Ordinary_X_table[1];
    };
    const uint64_t _General_precision_tables_2<double>::_Special_X_table[1] = {0};
    const uint64_t _General_precision_tables_2<double>::_Ordinary_X_table[1] = {0};
}
