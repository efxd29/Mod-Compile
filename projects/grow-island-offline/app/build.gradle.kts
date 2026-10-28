plugins {
    id("com.android.application")
}

android {
    namespace = "com.personal.growislandoffline"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.personal.growislandoffline"
        minSdk = 23
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
        }
    }
}

dependencies {
    implementation("androidx.webkit:webkit:1.12.1")
}
