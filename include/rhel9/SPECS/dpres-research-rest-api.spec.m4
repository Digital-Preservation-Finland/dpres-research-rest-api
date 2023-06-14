# vim:ft=spec

%define file_prefix M4_FILE_PREFIX
%define file_ext M4_FILE_EXT

%define file_version M4_FILE_VERSION
%define file_release_tag %{nil}M4_FILE_RELEASE_TAG
%define file_release_number M4_FILE_RELEASE_NUMBER
%define file_build_number M4_FILE_BUILD_NUMBER
%define file_commit_ref M4_FILE_COMMIT_REF

Name:           python-dpres-research-rest-api
Version:        %{file_version}
Release:        %{file_release_number}%{file_release_tag}.%{file_build_number}.git%{file_commit_ref}%{?dist}
Summary:        REST API for metadata validation and SIP creation triggering
License:        LGPLv3+
URL:            https://www.digitalpreservation.fi
Source0:        %{file_prefix}-v%{file_version}%{?file_release_tag}-%{file_build_number}-g%{file_commit_ref}.%{file_ext}
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  %{py3_dist mongomock}
BuildRequires:  %{py3_dist pip}
BuildRequires:  %{py3_dist pytest-mock}
BuildRequires:  %{py3_dist requests_mock}
BuildRequires:  %{py3_dist setuptools}
BuildRequires:  %{py3_dist setuptools_scm}
BuildRequires:  %{py3_dist tuspy}
BuildRequires:  %{py3_dist upload_rest_api}
BuildRequires:  %{py3_dist wheel}

%global _description %{expand:
REST API for metadata validation and SIP creation triggering
}

%description %_description

%package -n python3-dpres-research-rest-api
Summary: %{summary}
Requires: %{py3_dist metax-access}
Requires: %{py3_dist siptools-research}

%description -n python3-dpres-research-rest-api %_description

%prep
%autosetup -n %{file_prefix}-v%{file_version}%{?file_release_tag}-%{file_build_number}-g%{file_commit_ref}

%build
export SETUPTOOLS_SCM_PRETEND_VERSION=%{file_version}
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files dpres_research_rest_api

%files -n python3-dpres-research-rest-api -f %{pyproject_files}
%license LICENSE
%doc README.rst

# TODO: For now changelog must be last, because it is generated automatically
# from git log command. Appending should be fixed to happen only after %changelog macro
%changelog
