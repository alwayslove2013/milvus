// Copyright (C) 2019-2020 Zilliz. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software distributed under the License
// is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
// or implied. See the License for the specific language governing permissions and limitations under the License.

package funcutil

// SetContain returns true if set m1 contains set m2
func SetContain(m1, m2 map[interface{}]struct{}) bool {
	if len(m1) < len(m2) {
		return false
	}

	for k2 := range m2 {
		_, ok := m1[k2]
		if !ok {
			return false
		}
	}

	return true
}
