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

package storage

import (
	"errors"
	"io/ioutil"
	"os"
	"path"

	"golang.org/x/exp/mmap"

	"github.com/milvus-io/milvus/internal/log"
)

type LocalChunkManager struct {
	localPath string
}

func NewLocalChunkManager(localPath string) *LocalChunkManager {
	return &LocalChunkManager{
		localPath: localPath,
	}
}

func (lcm *LocalChunkManager) GetPath(key string) (string, error) {
	if !lcm.Exist(key) {
		return "", errors.New("local file cannot be found with key:" + key)
	}
	path := path.Join(lcm.localPath, key)
	return path, nil
}

func (lcm *LocalChunkManager) Write(key string, content []byte) error {
	filePath := path.Join(lcm.localPath, key)
	dir := path.Dir(filePath)
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		err := os.MkdirAll(dir, os.ModePerm)
		if err != nil {
			return err
		}
	}
	err := ioutil.WriteFile(filePath, content, 0644)
	if err != nil {
		return err
	}
	return nil
}

func (lcm *LocalChunkManager) Exist(key string) bool {
	path := path.Join(lcm.localPath, key)
	_, err := os.Stat(path)
	if err != nil {
		return os.IsExist(err)
	}
	return true
}

func (lcm *LocalChunkManager) Read(key string) ([]byte, error) {
	path := path.Join(lcm.localPath, key)
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	content, err := ioutil.ReadAll(file)
	if err != nil {
		return nil, err
	}
	return content, nil
}

func (lcm *LocalChunkManager) ReadAt(key string, p []byte, off int64) (n int, err error) {
	path := path.Join(lcm.localPath, key)
	at, err := mmap.Open(path)
	defer func() {
		if at != nil {
			err = at.Close()
			if err != nil {
				log.Error(err.Error())
			}
		}
	}()
	if err != nil {
		return 0, err
	}

	return at.ReadAt(p, off)
}
